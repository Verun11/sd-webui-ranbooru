import os
import sys
import random
import types
import html
import requests_cache
from PIL import Image, UnidentifiedImageError
from io import BytesIO
import shutil

# --- Ranbooru.py Source Code (from Turn 49, with added prints for debugging) ---
ranbooru_py_content = """
from io import BytesIO
import html
import random
import requests
import re
import modules.scripts as scripts
import gradio as gr
import os
from PIL import Image
import numpy as np
import importlib
import requests_cache

from modules.processing import process_images, StableDiffusionProcessingImg2Img
from modules import shared
from modules.sd_hijack import model_hijack
from modules import deepbooru
from modules.ui_components import InputAccordion

extension_root = scripts.basedir()
user_data_dir = os.path.join(extension_root, 'user')
user_search_dir = os.path.join(user_data_dir, 'search')
user_remove_dir = os.path.join(user_data_dir, 'remove')
user_forbidden_prompt_dir = os.path.join(user_data_dir, 'forbidden_prompt')
user_wildcards_dir = os.path.join(user_data_dir, 'wildcards')
os.makedirs(user_search_dir, exist_ok=True)
os.makedirs(user_remove_dir, exist_ok=True)
os.makedirs(user_forbidden_prompt_dir, exist_ok=True)
os.makedirs(user_wildcards_dir, exist_ok=True)

if not os.path.isfile(os.path.join(user_search_dir, 'tags_search.txt')):
    with open(os.path.join(user_search_dir, 'tags_search.txt'), 'w'):
        pass
if not os.path.isfile(os.path.join(user_remove_dir, 'tags_remove.txt')):
    with open(os.path.join(user_remove_dir, 'tags_remove.txt'), 'w'):
        pass
# This default file creation in ranbooru.py will be preempted by the test runner creating the file first.
if not os.path.isfile(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt')):
    with open(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt'), 'w') as f:
        f.write("# Add tags here, one per line\\n")
        f.write("artist_name_example\\n")
        f.write("character_name_example\\n")

COLORED_BG = ['black_background', 'aqua_background', 'white_background', 'colored_background', 'gray_background', 'blue_background', 'green_background', 'red_background', 'brown_background', 'purple_background', 'yellow_background', 'orange_background', 'pink_background', 'plain', 'transparent_background', 'simple_background', 'two-tone_background', 'grey_background']
ADD_BG = ['outdoors', 'indoors']
BW_BG = ['monochrome', 'greyscale', 'grayscale']
POST_AMOUNT = 100
COUNT = 100
DEBUG = False
RATING_TYPES = {
    "none": {"All": "All"},
    "full": {"All": "All", "Safe": "safe", "Questionable": "questionable", "Explicit": "explicit"},
    "single": {"All": "All", "Safe": "g", "Sensitive": "s", "Questionable": "q", "Explicit": "e"}
}
RATINGS = {
    "e621": RATING_TYPES['full'], "danbooru": RATING_TYPES['single'], "aibooru": RATING_TYPES['full'],
    "yande.re": RATING_TYPES['full'], "konachan": RATING_TYPES['full'], "safebooru": RATING_TYPES['none'],
    "rule34": RATING_TYPES['full'], "xbooru": RATING_TYPES['full'], "gelbooru": RATING_TYPES['single']
}

def get_available_ratings(booru):
    return gr.Radio.update(choices=RATINGS[booru].keys(), value="All")

def show_fringe_benefits(booru):
    return gr.Checkbox.update(visible=(booru == 'gelbooru'))

def check_exception(booru, parameters):
    post_id = parameters.get('post_id')
    tags = parameters.get('tags')
    if booru == 'konachan' and post_id: raise Exception("Konachan does not support post IDs")
    if booru == 'yande.re' and post_id: raise Exception("Yande.re does not support post IDs")
    if booru == 'e621' and post_id: raise Exception("e621 does not support post IDs")
    if booru == 'danbooru' and tags and len(tags.split(',')) > 1:
        raise Exception("Danbooru does not support multiple tags. You can have only one tag.")

class Booru():
    def __init__(self, booru, booru_url):
        self.booru = booru
        self.booru_url = booru_url
        self.headers = {'user-agent': 'my-app/0.0.1'}
    def get_data(self, add_tags, max_pages=10, id=''): return {'post': []}
    def get_post(self, add_tags, max_pages=10, id=''): return {'post': []}

class Gelbooru(Booru):
    def __init__(self, fringe_benefits): super().__init__('gelbooru', ''); self.fringeBenefits = fringe_benefits
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT=0; return {'@attributes': {'count':0}, 'post':[]}
class XBooru(Booru):
    def __init__(self): super().__init__('xbooru', '')
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT=0; return {'post':[]}
class Rule34(Booru):
    def __init__(self): super().__init__('rule34', '')
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT=0; return {'post':[]}
class Safebooru(Booru):
    def __init__(self): super().__init__('safebooru', '')
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT=0; return {'post':[]}
class Konachan(Booru):
    def __init__(self): super().__init__('konachan', '')
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT=0; return {'post':[]}
class Yandere(Booru):
    def __init__(self): super().__init__('yande.re', '')
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT=0; return {'post':[]}
class AIBooru(Booru):
    def __init__(self): super().__init__('AIBooru', '')
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT=0; return {'post':[]}
class Danbooru(Booru):
    def __init__(self): super().__init__('danbooru', '')
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT=0; return {'post':[]}
    def get_post(self, add_tags, max_pages=10, id=''): return {'post': []}
class e621(Booru):
    def __init__(self): super().__init__('e621', '')
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT=0; return {'posts':[]}
    def get_post(self, add_tags, max_pages=10, id=''): return {'post': {}}


def generate_chaos(pos_tags, neg_tags, chaos_amount):
    chaos_list = [tag for tag in pos_tags.split(',') + neg_tags.split(',') if tag.strip() != '']
    chaos_list = list(set(chaos_list)); random.shuffle(chaos_list)
    len_list = round(len(chaos_list) * chaos_amount)
    pos_prompt = ','.join(chaos_list[len_list:])
    neg_prompt = ','.join(chaos_list[:len_list])
    return pos_prompt, neg_prompt

def resize_image(img, width, height, cropping=True): return img
def modify_prompt(prompt, tagged_prompt, type_deepbooru):
    if type_deepbooru == 'Add Before': return tagged_prompt + ',' + prompt
    elif type_deepbooru == 'Add After': return prompt + ',' + tagged_prompt
    elif type_deepbooru == 'Replace': return tagged_prompt
    return prompt
def remove_repeated_tags(prompt):
    prompt_list = prompt.split(','); new_prompt = []
    for tag in prompt_list:
        if tag not in new_prompt: new_prompt.append(tag)
    return ','.join(new_prompt)
def limit_prompt_tags(prompt, limit_tags, mode):
    clean_prompt = prompt.split(',')
    if mode == 'Limit': clean_prompt = clean_prompt[:int(len(clean_prompt) * limit_tags)]
    elif mode == 'Max': clean_prompt = clean_prompt[:limit_tags]
    return ','.join(clean_prompt)

class Script(scripts.Script):
    previous_loras = ''; last_img = []; real_steps = 0; version = "1.2"; original_prompt = ''
    use_img2img_flag = False; use_ip_flag = False; enabled_flag = False
    denoising_strength = 0.75; use_deepbooru_flag = False; type_deepbooru_val = "Add Before"
    crop_center_flag = False; use_last_img_flag = False

    def process_wildcards(self, current_tags_string):
        import re; import os; import random
        processed_tags = current_tags_string
        while True:
            match = re.search(r'__([a-zA-Z0-9_]+)__', processed_tags)
            if not match: break
            keyword = match.group(1); wildcard_to_replace = match.group(0); replacement_tag = ""
            file_path = os.path.join(user_wildcards_dir, f"{keyword}.txt")
            if os.path.exists(file_path) and os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        possible_tags = [line.strip() for line in f if line.strip()]
                    if possible_tags: replacement_tag = random.choice(possible_tags)
                except Exception as e: print(f"[Ranbooru] Error reading wildcard file {file_path}: {e}")
            processed_tags = processed_tags.replace(wildcard_to_replace, replacement_tag, 1)
        return ','.join([tag.strip() for tag in processed_tags.split(',') if tag.strip()])

    def get_files(self, path):
        files = [];
        if os.path.exists(path):
            for file in os.listdir(path):
                if file.endswith('.txt'): files.append(file)
        return files

    def hide_object(self, obj, booru_val):
        if hasattr(obj, 'interactive'):
             if booru_val == 'konachan' or booru_val == 'yande.re': obj.interactive = False
             else: obj.interactive = True

    def title(self): return "Ranbooru"
    def show(self, is_img2img): return scripts.AlwaysVisible
    def refresh_ser(self): return gr.update(choices=self.get_files(user_search_dir))
    def refresh_rem(self): return gr.update(choices=self.get_files(user_remove_dir))

    def get_forbidden_files(self):
        os.makedirs(user_forbidden_prompt_dir, exist_ok=True)
        files = [f for f in os.listdir(user_forbidden_prompt_dir) if f.endswith('.txt')]
        default_file = 'tags_forbidden.txt'
        default_file_path = os.path.join(user_forbidden_prompt_dir, default_file)
        if not files and not os.path.exists(default_file_path):
            with open(default_file_path, 'w') as f: f.write("# Add tags here, one per line\\nartist_name_example\\ncharacter_name_example\\n")
            files.append(default_file)
        elif default_file not in files and not os.path.exists(default_file_path):
             with open(default_file_path, 'w') as f: f.write("# Add tags here, one per line\\nartist_name_example\\ncharacter_name_example\\n")
        if default_file not in files and os.path.exists(default_file_path): files.append(default_file)
        return files if files else [default_file]

    def refresh_forbidden_files(self): return gr.update(choices=self.get_forbidden_files())
    def ui(self, is_img2img): return [None]*48
    def check_orientation(self, img):
        x, y = img.size
        if x / y > 1.2: return [768, 512]
        elif y / x > 1.2: return [512, 768]
        else: return [768, 768]

    def loranado(self, lora_enabled, lora_folder, lora_amount, lora_min, lora_max, lora_custom_weights, p, lora_lock_prev):
        lora_prompt = ''
        if lora_enabled and lora_folder:
            mock_loras = ["lora1", "lora2", "lora3"]
            loras_path = os.path.join("models/Lora", lora_folder)
            if hasattr(shared, 'cmd_opts') and hasattr(shared.cmd_opts, 'lora_dir'):
                 loras_path = os.path.join(shared.cmd_opts.lora_dir, lora_folder)
            if not os.path.exists(loras_path): print(f"LoRA folder not found: {loras_path}, using mocks."); loras_in_folder = mock_loras
            else: loras_in_folder = [f.replace('.safetensors', '') for f in os.listdir(loras_path) if f.endswith('.safetensors')]
            if not loras_in_folder: loras_in_folder = mock_loras
            if lora_lock_prev: lora_prompt = self.previous_loras
            else:
                selected_loras_for_prompt = []
                for i in range(0, lora_amount):
                    lora_weight = 0; custom_weights_list = lora_custom_weights.split(',')
                    if lora_custom_weights != '' and i < len(custom_weights_list):
                        try: lora_weight = float(custom_weights_list[i])
                        except ValueError: lora_weight = round(random.uniform(lora_min, lora_max), 1)
                    else: lora_weight = round(random.uniform(lora_min, lora_max), 1)
                    if lora_weight == 0 and (lora_min != 0 or lora_max != 0):
                        lora_weight = round(random.uniform(lora_min, lora_max), 1)
                        if lora_weight == 0 and (lora_min !=0 or lora_max !=0) : lora_weight = lora_max
                    if loras_in_folder: selected_loras_for_prompt.append(f'<lora:{random.choice(loras_in_folder)}:{lora_weight}>')
                lora_prompt = "".join(selected_loras_for_prompt)
                self.previous_loras = lora_prompt
        if lora_prompt:
            if isinstance(p.prompt, list):
                for num, pr_item in enumerate(p.prompt): p.prompt[num] = f'{lora_prompt} {pr_item}'
            else: p.prompt = f'{lora_prompt} {p.prompt}'
        return p

    MOCK_BOORU_POST_TAGS = ["mock_ranbooru_tag"]

    def before_process(self, p, enabled, tags, booru, remove_bad_tags, max_pages, change_dash, same_prompt, fringe_benefits, remove_tags, use_img2img, denoising, use_last_img, change_background, change_color, shuffle_tags, post_id, mix_prompt, mix_amount, chaos_mode, negative_mode, chaos_amount, limit_tags_percentage, max_tags_count, sorting_order, mature_rating, lora_folder, lora_amount, lora_min, lora_max, lora_enabled_ui, lora_custom_weights, lora_lock_prev, use_ip, use_search_txt, use_remove_txt, choose_search_txt, choose_remove_txt, search_refresh_btn_dummy, remove_refresh_btn_dummy, forbidden_prompt_tags_text, use_forbidden_prompt_txt, choose_forbidden_prompt_txt, crop_center, use_deepbooru, type_deepbooru, use_same_seed, use_cache, disable_prompt_modification):
        self.use_img2img_flag = use_img2img; self.use_ip_flag = use_ip; self.enabled_flag = enabled
        self.denoising_strength = denoising; self.use_deepbooru_flag = use_deepbooru
        self.type_deepbooru_val = type_deepbooru; self.crop_center_flag = crop_center
        self.use_last_img_flag = use_last_img

        if use_cache and not requests_cache.patcher.is_installed(): requests_cache.install_cache('ranbooru_cache', backend='sqlite', expire_after=3600)
        elif not use_cache and requests_cache.patcher.is_installed(): requests_cache.uninstall_cache()

        if not enabled:
            if lora_enabled_ui: p = self.loranado(lora_enabled_ui, lora_folder, lora_amount, lora_min, lora_max, lora_custom_weights, p, lora_lock_prev)
            return

        if disable_prompt_modification:
            if lora_enabled_ui: p = self.loranado(lora_enabled_ui, lora_folder, lora_amount, lora_min, lora_max, lora_custom_weights, p, lora_lock_prev)
            return

        booru_apis = {
            'gelbooru': Gelbooru(fringe_benefits), 'rule34': Rule34(), 'safebooru': Safebooru(),
            'danbooru': Danbooru(), 'konachan': Konachan(), 'yande.re': Yandere(),
            'aibooru': AIBooru(), 'xbooru': XBooru(), 'e621': e621(),
        }
        self.original_prompt = str(p.prompt)
        tags_from_ui = self.process_wildcards(tags)
        check_exception(booru, {'tags': tags_from_ui, 'post_id': post_id})

        current_processing_prompt = str(self.original_prompt)

        current_bad_tags = []
        if remove_bad_tags: current_bad_tags.extend(['mixed-language_text', 'watermark', 'text', 'english_text', 'speech_bubble', 'signature', 'artist_name', 'censored', 'bar_censor', 'translation', 'twitter_username', "twitter_logo", 'patreon_username', 'commentary_request', 'tagme', 'commentary', 'character_name', 'mosaic_censoring', 'instagram_username', 'text_focus', 'english_commentary', 'comic', 'translation_request', 'fake_text', 'translated', 'paid_reward_available', 'thought_bubble', 'multiple_views', 'silent_comic', 'out-of-frame_censoring', 'symbol-only_commentary', '3koma', '2koma', 'character_watermark', 'spoken_question_mark', 'japanese_text', 'spanish_text', 'language_text', 'fanbox_username', 'commission', 'original', 'ai_generated', 'stable_diffusion', 'tagme_(artist)', 'text_bubble', 'qr_code', 'chinese_commentary', 'korean_text', 'partial_commentary', 'chinese_text', 'copyright_request', 'heart_censor', 'censored_nipples', 'page_number', 'scan', 'fake_magazine_cover', 'korean_commentary'])

        background_options = {'Add Background': (random.choice(ADD_BG) + ',detailed_background', COLORED_BG), 'Remove Background': ('plain_background,simple_background,' + random.choice(COLORED_BG), ADD_BG), 'Remove All': ('', COLORED_BG + ADD_BG)}
        if change_background in background_options:
            prompt_addition, tags_to_remove_bg = background_options[change_background]
            current_bad_tags.extend(tags_to_remove_bg)
            if prompt_addition: current_processing_prompt = f'{current_processing_prompt.strip()},{prompt_addition}' if current_processing_prompt.strip() else prompt_addition

        color_options = {'Colored': (None, BW_BG), 'Limited Palette': ('(limited_palette:1.3)', None), 'Monochrome': (','.join(BW_BG), None)}
        if change_color in color_options:
            prompt_addition_color, tags_to_remove_color = color_options[change_color]
            if tags_to_remove_color: current_bad_tags.extend(tags_to_remove_color)
            if prompt_addition_color: current_processing_prompt = f'{current_processing_prompt.strip()},{prompt_addition_color}' if current_processing_prompt.strip() else prompt_addition_color

        ranbooru_prompts_collection = []
        num_images_to_generate = p.batch_size * p.n_iter

        for i in range(num_images_to_generate):
            mock_tags_for_this_iteration = list(self.MOCK_BOORU_POST_TAGS)
            if same_prompt and i > 0 and ranbooru_prompts_collection:
                 mock_tags_for_this_iteration = ranbooru_prompts_collection[0].split(',')
            current_mock_tags = list(mock_tags_for_this_iteration)
            if shuffle_tags: random.shuffle(current_mock_tags)
            ranbooru_prompts_collection.append(",".join(tag for tag in current_mock_tags if tag))

        global last_img; last_img = []

        all_bad_tags = list(set(current_bad_tags))
        if remove_tags:
            if ',' in remove_tags: all_bad_tags.extend(tag.strip() for tag in remove_tags.split(',') if tag.strip())
            elif remove_tags.strip() : all_bad_tags.append(remove_tags.strip())
        if use_remove_txt and choose_remove_txt:
            try:
                remove_file_path = os.path.join(user_remove_dir, choose_remove_txt)
                if os.path.exists(remove_file_path):
                    with open(remove_file_path, 'r', encoding='utf-8') as f:
                        all_bad_tags.extend(tag.strip() for tag in f.read().split(',') if tag.strip())
            except Exception as e: print(f"Error reading remove_tags file: {e}")

        cleaned_ranbooru_prompts = []
        for rp_item in ranbooru_prompts_collection:
            tags_list = [tag for tag in html.unescape(rp_item).split(',') if tag.strip()]
            final_tags_for_rp = []
            for tag_item in tags_list:
                is_bad = False
                for bad_tag_item in all_bad_tags:
                    if '*' in bad_tag_item and bad_tag_item.replace('*', '') in tag_item: is_bad = True; break
                    elif bad_tag_item == tag_item: is_bad = True; break
                if not is_bad: final_tags_for_rp.append(tag_item)
            new_prompt_str = ','.join(final_tags_for_rp)
            if change_dash: new_prompt_str = new_prompt_str.replace("_", " ")
            cleaned_ranbooru_prompts.append(new_prompt_str)
        ranbooru_prompts = cleaned_ranbooru_prompts

        # --- BEGIN MOVED AND MODIFIED FORBIDDEN PROMPT TAGS FILTERING (applies only to ranbooru_prompts) ---
        # print(f"[DEBUG] Ranbooru prompts BEFORE forbidden filter: {ranbooru_prompts}")
        forbidden_tags_to_apply = set()
        if forbidden_prompt_tags_text:
            forbidden_tags_to_apply.update(tag.strip().lower() for tag in forbidden_prompt_tags_text.split(',') if tag.strip())
        if use_forbidden_prompt_txt and choose_forbidden_prompt_txt:
            try:
                forbidden_file_path = os.path.join(user_forbidden_prompt_dir, choose_forbidden_prompt_txt)
                # print(f"[DEBUG] Reading forbidden tags from: {forbidden_file_path}")
                if os.path.exists(forbidden_file_path):
                    with open(forbidden_file_path, 'r', encoding='utf-8') as f:
                        forbidden_tags_to_apply.update(line.strip().lower() for line in f if line.strip())
            except Exception as e: print(f"Error reading chosen forbidden tags file {choose_forbidden_prompt_txt}: {e}")

        # print(f"[DEBUG] Forbidden tags to apply: {forbidden_tags_to_apply}")

        if forbidden_tags_to_apply:
            filtered_ranbooru_prompts_final = []
            for tag_string in ranbooru_prompts:
                tags_list = [tag.strip() for tag in tag_string.split(',') if tag.strip()]
                kept_tags = [tag for tag in tags_list if tag.lower() not in forbidden_tags_to_apply]
                filtered_ranbooru_prompts_final.append(','.join(kept_tags))
            ranbooru_prompts = filtered_ranbooru_prompts_final
        # print(f"[DEBUG] Ranbooru prompts AFTER forbidden filter: {ranbooru_prompts}")
        # --- END MOVED AND MODIFIED FORBIDDEN PROMPT TAGS FILTERING ---

        user_base_prompt = current_processing_prompt.strip()

        if len(ranbooru_prompts) == 1:
            ranbooru_tags_to_add = ranbooru_prompts[0]
            if user_base_prompt and ranbooru_tags_to_add: p.prompt = f"{user_base_prompt},{ranbooru_tags_to_add}"
            elif ranbooru_tags_to_add: p.prompt = ranbooru_tags_to_add
            else: p.prompt = user_base_prompt
            if chaos_mode in ['Chaos', 'Less Chaos']:
                base_neg_for_chaos = str(p.negative_prompt) if chaos_mode == 'Chaos' else ''
                p.prompt, generated_chaos_neg_tags = generate_chaos(str(p.prompt), base_neg_for_chaos, chaos_amount)
                current_neg_prompt = str(p.negative_prompt)
                if current_neg_prompt and generated_chaos_neg_tags: p.negative_prompt = f"{current_neg_prompt},{generated_chaos_neg_tags}"
                elif generated_chaos_neg_tags: p.negative_prompt = generated_chaos_neg_tags
        else:
            base_neg_prompt_from_ui = str(p.negative_prompt)
            if chaos_mode == 'Chaos':
                processed_ranbooru_for_chaos = []; new_negative_prompts_list = []
                for rp_item in ranbooru_prompts:
                    tmp_pos, tmp_neg = generate_chaos(rp_item, base_neg_prompt_from_ui, chaos_amount)
                    processed_ranbooru_for_chaos.append(tmp_pos); new_negative_prompts_list.append(tmp_neg)
                ranbooru_prompts = processed_ranbooru_for_chaos; p.negative_prompt = new_negative_prompts_list
            elif chaos_mode == 'Less Chaos':
                processed_ranbooru_for_chaos = []; new_negative_prompts_list = []
                for rp_item in ranbooru_prompts:
                    tmp_pos, tmp_neg_chaos_only = generate_chaos(rp_item, "", chaos_amount)
                    processed_ranbooru_for_chaos.append(tmp_pos)
                    current_neg = f"{base_neg_prompt_from_ui.strip()},{tmp_neg_chaos_only}" if base_neg_prompt_from_ui.strip() and tmp_neg_chaos_only else (base_neg_prompt_from_ui.strip() or tmp_neg_chaos_only or "")
                    new_negative_prompts_list.append(current_neg.strip(','))
                ranbooru_prompts = processed_ranbooru_for_chaos; p.negative_prompt = new_negative_prompts_list
            else: p.negative_prompt = [base_neg_prompt_from_ui for _ in range(len(ranbooru_prompts))]

            final_batch_prompts = []
            for rp_item in ranbooru_prompts:
                if user_base_prompt and rp_item: final_batch_prompts.append(f"{user_base_prompt},{rp_item}")
                elif rp_item: final_batch_prompts.append(rp_item)
                else: final_batch_prompts.append(user_base_prompt)
            p.prompt = final_batch_prompts

        if negative_mode == 'Negative':
            user_base_prompt_tags_set = set(tag.strip().lower() for tag in user_base_prompt.split(',') if tag.strip())
            if isinstance(p.prompt, list):
                new_positive_prompts_neg = []; new_negative_prompts_neg = []
                current_neg_prompts = p.negative_prompt if isinstance(p.negative_prompt, list) else [str(p.negative_prompt)] * len(p.prompt)
                for i, full_prompt_str in enumerate(p.prompt):
                    current_prompt_tags = [tag.strip() for tag in full_prompt_str.split(',') if tag.strip()]
                    tags_to_move_to_negative = [tag for tag in current_prompt_tags if tag.lower() not in user_base_prompt_tags_set]
                    new_positive_prompts_neg.append(user_base_prompt)
                    additional_neg = ",".join(tags_to_move_to_negative)
                    current_neg = current_neg_prompts[i] if i < len(current_neg_prompts) else str(p.negative_prompt)
                    new_negative_prompts_neg.append(f"{current_neg},{additional_neg}".strip(','))
                p.prompt = new_positive_prompts_neg; p.negative_prompt = new_negative_prompts_neg
            elif isinstance(p.prompt, str):
                current_prompt_tags = [tag.strip() for tag in p.prompt.split(',') if tag.strip()]
                tags_to_move_to_negative = [tag for tag in current_prompt_tags if tag.lower() not in user_base_prompt_tags_set]
                p.prompt = user_base_prompt
                additional_neg = ",".join(tags_to_move_to_negative)
                p.negative_prompt = f"{str(p.negative_prompt)},{additional_neg}".strip(',')

        if isinstance(p.negative_prompt, list) and len(p.negative_prompt) > 1 :
            neg_prompt_tokens = [model_hijack.get_prompt_lengths(pr_item)[1] for pr_item in p.negative_prompt]
            if len(set(neg_prompt_tokens)) != 1:
                print('Padding negative prompts'); max_tokens = max(neg_prompt_tokens)
                for num, neg_len in enumerate(neg_prompt_tokens):
                    while neg_len < max_tokens:
                        current_neg_prompt_item_parts = p.negative_prompt[num].split(',')
                        p.negative_prompt[num] += ("," + random.choice(current_neg_prompt_item_parts)) if current_neg_prompt_item_parts and current_neg_prompt_item_parts[0] else ",_"
                        neg_len = model_hijack.get_prompt_lengths(p.negative_prompt[num])[1]

        if limit_tags_percentage < 1:
            if isinstance(p.prompt, list): p.prompt = [limit_prompt_tags(pr_item, limit_tags_percentage, 'Limit') for pr_item in p.prompt]
            else: p.prompt = limit_prompt_tags(p.prompt, limit_tags_percentage, 'Limit')
        if max_tags_count > 0:
            if isinstance(p.prompt, list): p.prompt = [limit_prompt_tags(pr_item, max_tags_count, 'Max') for pr_item in p.prompt]
            else: p.prompt = limit_prompt_tags(p.prompt, max_tags_count, 'Max')

        if use_same_seed:
            p.seed = random.randint(0, 2**32 - 1) if not hasattr(p,'seed') or p.seed == -1 else p.seed
            p.seed = [p.seed] * (p.batch_size if hasattr(p,'batch_size') and p.batch_size is not None else 1)

        p = self.loranado(lora_enabled_ui, lora_folder, lora_amount, lora_min, lora_max, lora_custom_weights, p, lora_lock_prev)

        if use_deepbooru and not use_img2img:
            if last_img : self.last_img = last_img
            else: print("DeepBooru selected but no images were fetched/available for tagging.")
            if self.last_img:
                tagged_prompts = self.use_autotagger('deepbooru')
                if isinstance(p.prompt, list):
                    if len(tagged_prompts) < len(p.prompt): tagged_prompts.extend([tagged_prompts[-1] if tagged_prompts else ""] * (len(p.prompt) - len(tagged_prompts)))
                    p.prompt = [modify_prompt(p.prompt[i], tagged_prompts[i], type_deepbooru) for i in range(len(p.prompt))]
                    p.prompt = [remove_repeated_tags(pr_item) for pr_item in p.prompt]
                else:
                    p.prompt = modify_prompt(p.prompt, tagged_prompts[0] if tagged_prompts else "", type_deepbooru)
                    p.prompt = remove_repeated_tags(p.prompt)

        if use_img2img:
            if not use_ip:
                self.real_steps = p.steps if hasattr(p,'steps') else 20; p.steps = 1
                if last_img: self.last_img = last_img
                else: print("Img2Img selected but no images were fetched/available.")
            if use_ip and self.last_img:
                try:
                    controlNetModule = importlib.import_module('extensions.sd-webui-controlnet.scripts.external_code', 'external_code')
                    controlNetList = controlNetModule.get_all_units_in_processing(p)
                    if controlNetList:
                        copied_network = controlNetList[0].__dict__.copy()
                        copied_network['enabled'] = True; copied_network['weight'] = denoising
                        copied_network['image']['image'] = np.array(self.last_img[0])
                        controlNetModule.update_cn_script_in_processing(p, [copied_network] + controlNetList[1:])
                except ModuleNotFoundError: print("ControlNet module not found. Skipping Send to ControlNet.")
                except Exception as e: print(f"Error with ControlNet: {e}")

    def postprocess(self, p, processed, *args):
        use_img2img = getattr(self, 'use_img2img_flag', False)
        use_ip = getattr(self, 'use_ip_flag', False)
        enabled = getattr(self, 'enabled_flag', False)

        if use_img2img and not use_ip and enabled and hasattr(self,'last_img') and self.last_img:
            p_width = p.width if hasattr(p,'width') else 512
            p_height = p.height if hasattr(p,'height') else 512
            crop_center = getattr(self, 'crop_center_flag', False)
            if crop_center: self.last_img = [resize_image(img, p_width, p_height, cropping=True) for img in self.last_img]
            else:
                processed_last_img = []
                for img_item in self.last_img:
                    orient_width, orient_height = self.check_orientation(img_item)
                    processed_last_img.append(resize_image(img_item, orient_width, orient_height, cropping=False))
                self.last_img = processed_last_img
                if self.last_img: p_width, p_height = self.last_img[0].size

            final_prompts_for_img2img = p.prompt
            use_deepbooru = getattr(self, 'use_deepbooru_flag', False)
            type_deepbooru = getattr(self, 'type_deepbooru_val', "Add Before")
            if use_deepbooru:
                tagged_prompts = self.use_autotagger('deepbooru')
                if isinstance(p.prompt, list):
                    if len(tagged_prompts) < len(p.prompt): tagged_prompts.extend([""]*(len(p.prompt)-len(tagged_prompts)))
                    final_prompts_for_img2img = [modify_prompt(p.prompt[i], tagged_prompts[i], type_deepbooru) for i in range(len(p.prompt))]
                    final_prompts_for_img2img = [remove_repeated_tags(pr) for pr in final_prompts_for_img2img]
                else:
                    final_prompts_for_img2img = modify_prompt(p.prompt, tagged_prompts[0] if tagged_prompts else "", type_deepbooru)
                    final_prompts_for_img2img = remove_repeated_tags(final_prompts_for_img2img)

            p_img2img = StableDiffusionProcessingImg2Img(
                sd_model=shared.sd_model,
                outpath_samples=getattr(shared.opts, 'outdir_samples', './outputs/img2img-samples') or getattr(shared.opts, 'outdir_img2img_samples', './outputs/img2img-samples'),
                outpath_grids=getattr(shared.opts, 'outdir_grids', './outputs/img2img-grids') or getattr(shared.opts, 'outdir_img2img_grids', './outputs/img2img-grids'),
                prompt=final_prompts_for_img2img,
                negative_prompt=getattr(p,'negative_prompt',""),
                seed=getattr(p,'seed',-1), sampler_name=getattr(p,'sampler_name',"Euler a"),
                scheduler=getattr(p,'scheduler',None), batch_size=getattr(p,'batch_size',1),
                n_iter=getattr(p,'n_iter',1), steps=getattr(self, 'real_steps', getattr(p,'steps',20)),
                cfg_scale=getattr(p,'cfg_scale',7.0), width=p_width, height=p_height,
                init_images=self.last_img, denoising_strength=getattr(self, 'denoising_strength', 0.75)
            )
            proc = process_images(p_img2img)
            if not hasattr(processed, 'images'): processed.images = []
            if not hasattr(processed, 'infotexts'): processed.infotexts = []
            processed.images.extend(proc.images); processed.infotexts.extend(proc.infotexts)
            use_last_img = getattr(self, 'use_last_img_flag', False)
            if use_last_img:
                if self.last_img : processed.images.append(self.last_img[0])
            else: processed.images.extend(self.last_img)

    def random_number(self, sorting_order, size):
        global COUNT
        effective_count = max(1, COUNT if COUNT <= POST_AMOUNT else POST_AMOUNT)
        if size <= 0 : return []
        if size > effective_count : size = effective_count
        if sorting_order in ('High Score', 'Low Score') and effective_count > 0:
            weights = np.arange(effective_count, 0, -1); weights = weights / weights.sum()
            random_numbers = np.random.choice(np.arange(effective_count), size=min(size, effective_count), p=weights, replace=False)
        elif effective_count > 0 : random_numbers = random.sample(range(effective_count), min(size, effective_count))
        else: random_numbers = []
        return random_numbers.tolist() if isinstance(random_numbers, np.ndarray) else random_numbers

    def use_autotagger(self, model_name):
        if model_name == 'deepbooru' and hasattr(self, 'last_img') and self.last_img:
            original_prompts_for_tagging = []
            num_images = len(self.last_img)
            current_original_prompt = self.original_prompt
            if isinstance(current_original_prompt, str):
                original_prompts_for_tagging = [current_original_prompt] * num_images
            elif isinstance(current_original_prompt, list):
                original_prompts_for_tagging = current_original_prompt
                if len(original_prompts_for_tagging) < num_images:
                    last_val = original_prompts_for_tagging[-1] if original_prompts_for_tagging else ""
                    original_prompts_for_tagging.extend([last_val] * (num_images - len(original_prompts_for_tagging)))
                elif len(original_prompts_for_tagging) > num_images:
                    original_prompts_for_tagging = original_prompts_for_tagging[:num_images]
            else: original_prompts_for_tagging = [""] * num_images

            final_tagged_prompts = []
            try:
                deepbooru.model.start()
                for i in range(num_images):
                    base_p = str(original_prompts_for_tagging[i]) if i < len(original_prompts_for_tagging) else ""
                    final_tagged_prompts.append(base_p + ',' + deepbooru.model.tag_multi(self.last_img[i]))
            except Exception as e: print(f"Error during DeepBooru tagging: {e}")
            finally:
                if hasattr(deepbooru, 'model') and hasattr(deepbooru.model, 'stop'): deepbooru.model.stop()
            return final_tagged_prompts
        return []
"""

# --- Test Runner Setup ---
# Create user/forbidden_prompt directory and the tags_forbidden.txt file for tests
# This ensures it's created by this script's context, visible to os.path.isfile in ranbooru code
# test_user_forbidden_prompt_dir = os.path.abspath(os.path.join(".", "user", "forbidden_prompt")) # Defined later in exec_globals too
# os.makedirs(test_user_forbidden_prompt_dir, exist_ok=True)
# with open(os.path.join(test_user_forbidden_prompt_dir, "tags_forbidden.txt"), "w") as f:
#    f.write("forbidden_tag_alpha\n")
#    f.write("makima (chainsaw man)\n")
# print(f"Test runner created/updated {os.path.join(test_user_forbidden_prompt_dir, 'tags_forbidden.txt')}")
# This file creation is now done right before exec_globals are fully populated.

if not os.path.exists("modules"): os.makedirs("modules")
with open("modules/scripts.py", "w") as f: f.write("import os\ndef basedir(): return os.path.abspath('.')\nclass Script:\n    def title(self): return 'BaseDummyScript'\n    def show(self, is_img2img): return True\n    def ui(self, is_img2img): return []\n    def elem_id(self, name): return name\n")
with open("modules/processing.py", "w") as f: f.write("def process_images(*args, **kwargs): return type('ProcRes', (), {'images': [], 'infotexts': []})()\nclass StableDiffusionProcessingImg2Img: pass\n")
with open("modules/shared.py", "w") as f:
    f.write("""
class opts_cls: pass
opts = opts_cls()
opts.outdir_samples = "./outputs/samples"
opts.outdir_img2img_samples = "./outputs/img2img_samples"
opts.outdir_grids = "./outputs/grids"
opts.outdir_img2img_grids = "./outputs/img2img_grids"

class cmd_opts_cls: pass
cmd_opts = cmd_opts_cls()
cmd_opts.lora_dir = 'models/Lora'
cmd_opts.deepbooru_score_threshold = 0.5

sd_model = None
state = type('State', (), {'interrupted': False})()
""")
with open("modules/sd_hijack.py", "w") as f: f.write("class model_hijack:\n    @staticmethod\n    def get_prompt_lengths(prompt_text):\n        length = len(prompt_text.split(','))\n        return (length, (length // 75 + 1) * 75)\n")
with open("modules/deepbooru.py", "w") as f: f.write("class DeepDanbooru:\n    def start(self): pass\n    def stop(self): pass\n    def tag_multi(self, pil_image, threshold=0.5): return 'dummy_deepbooru_tag'\nmodel = DeepDanbooru()\n")
with open("modules/ui_components.py", "w") as f: f.write("import gradio as gr\nclass InputAccordion:\n    def __init__(self, open_by_default, label, elem_id=None): self.label = label\n    def __enter__(self): return self\n    def __exit__(self, exc_type, exc_val, exc_tb): pass\n")

sys.path.insert(0, os.path.abspath("."))
import modules.scripts
import modules.shared
import modules.processing
import modules.sd_hijack
import modules.deepbooru
import modules.ui_components

# Define user directories for the exec'd script
# These need to be absolute paths for os.path.join inside the exec'd code to work correctly from any CWD
base_app_dir = os.path.abspath(".")
mock_user_dir = os.path.join(base_app_dir, "user")
mock_user_forbidden_prompt_dir = os.path.join(mock_user_dir, "forbidden_prompt")
mock_user_wildcards_dir = os.path.join(mock_user_dir, "wildcards")
mock_user_remove_dir = os.path.join(mock_user_dir, "remove")
mock_user_search_dir = os.path.join(mock_user_dir, "search")

os.makedirs(mock_user_forbidden_prompt_dir, exist_ok=True)
os.makedirs(mock_user_wildcards_dir, exist_ok=True) # For process_wildcards
os.makedirs(mock_user_remove_dir, exist_ok=True) # For remove_tags file
os.makedirs(mock_user_search_dir, exist_ok=True) # For search_tags file

# Create the specific forbidden tags file for this test run
with open(os.path.join(mock_user_forbidden_prompt_dir, "tags_forbidden.txt"), "w") as f:
   f.write("forbidden_tag_alpha\n")
   f.write("makima (chainsaw man)\n")
print(f"Test runner CREATED {os.path.join(mock_user_forbidden_prompt_dir, 'tags_forbidden.txt')}")


exec_globals = {
    'Image': Image, 'BytesIO': BytesIO, 'html': html, 'requests_cache': requests_cache,
    '__file__': os.path.join(base_app_dir, 'scripts', 'ranbooru.py'), '__name__': 'scripts.ranbooru',
    'scripts': sys.modules['modules.scripts'], 'shared': sys.modules['modules.shared'],
    'deepbooru': sys.modules['modules.deepbooru'],
    # These globals are defined in ranbooru.py itself using the mocked scripts.basedir()
    # 'user_wildcards_dir': mock_user_wildcards_dir,
    # 'user_forbidden_prompt_dir': mock_user_forbidden_prompt_dir,
    # 'user_remove_dir': mock_user_remove_dir,
    # 'user_search_dir': mock_user_search_dir
}
exec(ranbooru_py_content, exec_globals)
print("Executed embedded ranbooru.py content dynamically.")
RanbooruScriptClass = exec_globals['Script']

class SimpleMockProcessing:
    def __init__(self, initial_prompt, initial_negative_prompt="", batch_size=1, n_iter=1, steps=20, seed=-1, sampler_name="Euler a", cfg_scale=7.0, width=512, height=512):
        self.prompt = initial_prompt; self.negative_prompt = initial_negative_prompt
        self.batch_size = batch_size; self.n_iter = n_iter; self.steps = steps
        self.seed = seed; self.sampler_name = sampler_name; self.cfg_scale = cfg_scale
        self.width = width; self.height = height; self.sd_model = None

default_args = {
    "enabled": True, "tags": "", "booru": "gelbooru", "remove_bad_tags": True, "max_pages": 1,
    "change_dash": False, "same_prompt": True, "fringe_benefits": False, "remove_tags": "",
    "use_img2img": False, "denoising": 0.75, "use_last_img": False,
    "change_background": "Don't Change", "change_color": "Don't Change",
    "shuffle_tags": False, "post_id": "", "mix_prompt": False, "mix_amount": 2,
    "chaos_mode": "None", "negative_mode": "None", "chaos_amount": 0.5,
    "limit_tags_percentage": 1.0, "max_tags_count": 100, "sorting_order": "Random",
    "mature_rating": "All", "lora_folder": "test_lora_folder", "lora_amount": 1, "lora_min": -1.0,
    "lora_max": 1.0, "lora_enabled_ui": False, "lora_custom_weights": "", "lora_lock_prev": False,
    "use_ip": False, "use_search_txt": False, "use_remove_txt": False,
    "choose_search_txt": "", "choose_remove_txt": "",
    "search_refresh_btn_dummy": None, "remove_refresh_btn_dummy": None,
    "forbidden_prompt_tags_text": "", "use_forbidden_prompt_txt": True,
    "choose_forbidden_prompt_txt": "tags_forbidden.txt",
    "crop_center": False, "use_deepbooru": False, "type_deepbooru": "Add Before",
    "use_same_seed": False, "use_cache": False, "disable_prompt_modification": False
}
scenarios = [
    {"name": "S1: User forbidden, Ranbooru clean", "p_prompt": "forbidden_tag_alpha, user_tag_1", "tags_arg": "", "mock_ranbooru_tags": ["ranbooru_tag_A"], "expected_final_p_prompt": "forbidden_tag_alpha,user_tag_1,ranbooru_tag_A"},
    {"name": "S2: User clean, Ranbooru forbidden", "p_prompt": "user_tag_2", "tags_arg": "", "mock_ranbooru_tags": ["forbidden_tag_alpha", "ranbooru_tag_B"], "expected_final_p_prompt": "user_tag_2,ranbooru_tag_B"},
    {"name": "S3: User (parens) forbidden, Ranbooru clean", "p_prompt": "makima (chainsaw man), user_tag_3", "tags_arg": "", "mock_ranbooru_tags": ["ranbooru_tag_C"], "expected_final_p_prompt": "makima (chainsaw man),user_tag_3,ranbooru_tag_C"},
    {"name": "S4: User clean, Ranbooru (parens) forbidden", "p_prompt": "user_tag_4", "tags_arg": "", "mock_ranbooru_tags": ["makima (chainsaw man)", "ranbooru_tag_D"], "expected_final_p_prompt": "user_tag_4,ranbooru_tag_D"},
    {"name": "S5: User forbidden, Ranbooru same forbidden", "p_prompt": "forbidden_tag_alpha, user_tag_5", "tags_arg": "", "mock_ranbooru_tags": ["forbidden_tag_alpha", "ranbooru_tag_E"], "expected_final_p_prompt": "forbidden_tag_alpha,user_tag_5,ranbooru_tag_E"},
    {"name": "S6: User clean, Ranbooru only forbidden", "p_prompt": "user_tag_6", "tags_arg": "", "mock_ranbooru_tags": ["forbidden_tag_alpha"], "expected_final_p_prompt": "user_tag_6"},
    {"name": "S7: User clean, Ranbooru empty after filter", "p_prompt": "user_tag_7", "tags_arg": "", "mock_ranbooru_tags": ["makima (chainsaw man)"], "expected_final_p_prompt": "user_tag_7"},
    {"name": "S8: User empty, Ranbooru forbidden", "p_prompt": "", "tags_arg": "", "mock_ranbooru_tags": ["forbidden_tag_alpha", "clean_ranbooru"], "expected_final_p_prompt": "clean_ranbooru"},
]

print("\nStarting Forbidden Tags Logic Test (Test Runner v5)...\n")
script_instance = RanbooruScriptClass()

# Ensure Lora mock folder exists if loranado is complex enough to need it
if hasattr(exec_globals.get('shared'), 'cmd_opts'):
    lora_models_path = exec_globals['shared'].cmd_opts.lora_dir
    os.makedirs(os.path.join(lora_models_path, "test_lora_folder"), exist_ok=True)

for scenario in scenarios:
    print(f"--- Running {scenario['name']} ---")
    p_mock = SimpleMockProcessing(initial_prompt=scenario["p_prompt"])
    current_args = default_args.copy()
    current_args["tags"] = scenario["tags_arg"]
    script_instance.MOCK_BOORU_POST_TAGS = scenario["mock_ranbooru_tags"]
    script_instance.before_process(p_mock, **current_args)

    final_prompt_str = p_mock.prompt
    if isinstance(p_mock.prompt, list): final_prompt_str = " |BATCH| ".join(p_mock.prompt)
    normalized_final_prompt = ",".join(sorted(filter(None, [tag.strip().lower() for tag in final_prompt_str.split(',')])))
    normalized_expected_prompt = ",".join(sorted(filter(None, [tag.strip().lower() for tag in scenario["expected_final_p_prompt"].split(',')])))

    print(f"  User Initial p.prompt: \"{scenario['p_prompt']}\"")
    print(f"  Ranbooru 'tags' arg (UI Search Pre): \"{scenario['tags_arg']}\"")
    print(f"  Mocked Ranbooru Fetched Tags (simulated): {scenario['mock_ranbooru_tags']}")
    print(f"  Expected Normalized p.prompt: \"{normalized_expected_prompt}\"")
    print(f"  Actual   Normalized p.prompt: \"{normalized_final_prompt}\"")

    if normalized_final_prompt == normalized_expected_prompt: print(f"  VERIFY PASS for {scenario['name']}.")
    else: print(f"  VERIFY FAIL for {scenario['name']}.")
    print("---")

if os.path.exists("modules"):
    try: shutil.rmtree("modules"); print("Cleaned up dummy modules directory.")
    except Exception as e: print(f"Error cleaning up dummy modules: {e}")
if os.path.exists(mock_user_dir): # Clean up user directory created for test files
    try: shutil.rmtree(mock_user_dir); print(f"Cleaned up mock user directory: {mock_user_dir}")
    except Exception as e: print(f"Error cleaning up {mock_user_dir}: {e}")
lora_base_path = os.path.abspath("models/Lora")
lora_test_folder = os.path.join(lora_base_path, "test_lora_folder")
if os.path.exists(lora_test_folder):
    try: shutil.rmtree(lora_test_folder);
    except Exception as e: print(f"Error cleaning up {lora_test_folder}: {e}")
if os.path.exists(lora_base_path) and not os.listdir(lora_base_path):
    try: os.rmdir(lora_base_path);
    except OSError : pass
if os.path.exists("models") and not os.listdir("models"):
    try: os.rmdir("models");
    except OSError: pass

print("\nTest execution finished.")
