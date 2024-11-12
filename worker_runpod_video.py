import os, shutil, json, requests, random, time, runpod
from urllib.parse import urlsplit

import torch
from PIL import Image
import numpy as np

import asyncio
import execution
import server
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
server_instance = server.PromptServer(loop)
execution.PromptQueue(server)

from nodes import load_custom_node
from nodes import NODE_CLASS_MAPPINGS
from comfy_extras import nodes_mask

load_custom_node("/content/ComfyUI/custom_nodes/ComfyUI_BiRefNet_ll")
load_custom_node("/content/ComfyUI/custom_nodes/add_text_2_img")
load_custom_node("/content/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite")

AutoDownloadBiRefNetModel = NODE_CLASS_MAPPINGS["AutoDownloadBiRefNetModel"]()
RembgByBiRefNet = NODE_CLASS_MAPPINGS["RembgByBiRefNet"]()
AddText = NODE_CLASS_MAPPINGS["AddText"]()
ImageCompositeMasked = nodes_mask.NODE_CLASS_MAPPINGS["ImageCompositeMasked"]()
VHS_LoadVideo = NODE_CLASS_MAPPINGS["VHS_LoadVideo"]()
VHS_VideoCombine = NODE_CLASS_MAPPINGS["VHS_VideoCombine"]()

with torch.inference_mode():
    model = AutoDownloadBiRefNetModel.load_model("General", "AUTO")[0]

def download_file(url, save_dir, file_name):
    os.makedirs(save_dir, exist_ok=True)
    original_file_name = url.split('/')[-1]
    _, original_file_extension = os.path.splitext(original_file_name)
    file_path = os.path.join(save_dir, file_name + original_file_extension)
    response = requests.get(url)
    response.raise_for_status()
    with open(file_path, 'wb') as file:
        file.write(response.content)
    return file_path

@torch.inference_mode()
def generate(input):
    values = input["input"]

    input_video=values['input_image_check']
    input_video=download_file(url=input_video, save_dir='/content/ComfyUI/input', file_name='input_image')
    text = values['text']
    x = values['x']
    y = values['y']
    font_size = values['font_size']
    font_family = values['font_family']
    font_color = values['font_color']
    font_shadow_x = values['font_shadow_x']
    font_shadow_y = values['font_shadow_y']
    shadow_color = values['shadow_color']
    custom_font_path = values['custom_font_path']
    custom_font_path=download_file(url=custom_font_path, save_dir='/content/ComfyUI/input', file_name='input_font')

    source, frame_count, audio, video_info = VHS_LoadVideo.load_video(video=input_video, force_rate=0, force_size="Disabled", custom_width=None, custom_height=None, frame_load_cap=0, skip_first_frames=0, select_every_nth=1)
    destination = AddText.add_text(image=source, text=text, x=x, y=y, font_size=font_size, font_family=font_family, font_color=font_color, font_shadow_x=font_shadow_x, font_shadow_y=font_shadow_y, shadow_color=shadow_color, custom_font_path=custom_font_path)[0]
    _, out_masks = RembgByBiRefNet.rem_bg(model=model, images=source)
    out_image = ImageCompositeMasked.composite(destination=destination, source=source, x=0, y=0, resize_source=False, mask=out_masks)[0]
    
    out_video = VHS_VideoCombine.combine_video(images=out_image, frame_rate=30, loop_count=0, filename_prefix="TextBehind", format="video/h264-mp4", save_output=True)
    source = out_video["result"][0][1][1]
    destination = '/content/ComfyUI/output/text-behind-video-tost.mp4'
    shutil.move(source, destination)

    result = f"/content/ComfyUI/output/text-behind-video-tost.mp4"
    try:
        notify_uri = values['notify_uri']
        del values['notify_uri']
        notify_token = values['notify_token']
        del values['notify_token']
        discord_id = values['discord_id']
        del values['discord_id']
        if(discord_id == "discord_id"):
            discord_id = os.getenv('com_camenduru_discord_id')
        discord_channel = values['discord_channel']
        del values['discord_channel']
        if(discord_channel == "discord_channel"):
            discord_channel = os.getenv('com_camenduru_discord_channel')
        discord_token = values['discord_token']
        del values['discord_token']
        if(discord_token == "discord_token"):
            discord_token = os.getenv('com_camenduru_discord_token')
        job_id = values['job_id']
        del values['job_id']
        default_filename = os.path.basename(result)
        with open(result, "rb") as file:
            files = {default_filename: file.read()}
        payload = {"content": f"{json.dumps(values)} <@{discord_id}>"}
        response = requests.post(
            f"https://discord.com/api/v9/channels/{discord_channel}/messages",
            data=payload,
            headers={"Authorization": f"Bot {discord_token}"},
            files=files
        )
        response.raise_for_status()
        result_url = response.json()['attachments'][0]['url']
        notify_payload = {"jobId": job_id, "result": result_url, "status": "DONE"}
        web_notify_uri = os.getenv('com_camenduru_web_notify_uri')
        web_notify_token = os.getenv('com_camenduru_web_notify_token')
        if(notify_uri == "notify_uri"):
            requests.post(web_notify_uri, data=json.dumps(notify_payload), headers={'Content-Type': 'application/json', "Authorization": web_notify_token})
        else:
            requests.post(web_notify_uri, data=json.dumps(notify_payload), headers={'Content-Type': 'application/json', "Authorization": web_notify_token})
            requests.post(notify_uri, data=json.dumps(notify_payload), headers={'Content-Type': 'application/json', "Authorization": notify_token})
        return {"jobId": job_id, "result": result_url, "status": "DONE"}
    except Exception as e:
        error_payload = {"jobId": job_id, "status": "FAILED"}
        try:
            if(notify_uri == "notify_uri"):
                requests.post(web_notify_uri, data=json.dumps(error_payload), headers={'Content-Type': 'application/json', "Authorization": web_notify_token})
            else:
                requests.post(web_notify_uri, data=json.dumps(error_payload), headers={'Content-Type': 'application/json', "Authorization": web_notify_token})
                requests.post(notify_uri, data=json.dumps(error_payload), headers={'Content-Type': 'application/json', "Authorization": notify_token})
        except:
            pass
        return {"jobId": job_id, "result": f"FAILED: {str(e)}", "status": "FAILED"}
    finally:
        if os.path.exists(result):
            os.remove(result)
        if os.path.exists(input_image):
            os.remove(input_image)

runpod.serverless.start({"handler": generate})