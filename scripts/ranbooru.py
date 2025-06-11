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
user_wildcards_dir = os.path.join(user_data_dir, 'wildcards') # Added wildcard directory
os.makedirs(user_search_dir, exist_ok=True)
os.makedirs(user_remove_dir, exist_ok=True)
os.makedirs(user_forbidden_prompt_dir, exist_ok=True)
os.makedirs(user_wildcards_dir, exist_ok=True) # Ensure wildcard directory is created

if not os.path.isfile(os.path.join(user_search_dir, 'tags_search.txt')):
    with open(os.path.join(user_search_dir, 'tags_search.txt'), 'w'):
        pass
if not os.path.isfile(os.path.join(user_remove_dir, 'tags_remove.txt')):
    with open(os.path.join(user_remove_dir, 'tags_remove.txt'), 'w'):
        pass
if not os.path.isfile(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt')):
    with open(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt'), 'w') as f:
        f.write("# Add tags here, one per line\n")
        f.write("artist_name_example\n")
        f.write("character_name_example\n")

COLORED_BG = ['black_background', 'aqua_background', 'white_background', 'colored_background', 'gray_background', 'blue_background', 'green_background', 'red_background', 'brown_background', 'purple_background', 'yellow_background', 'orange_background', 'pink_background', 'plain', 'transparent_background', 'simple_background', 'two-tone_background', 'grey_background']
ADD_BG = ['outdoors', 'indoors']
BW_BG = ['monochrome', 'greyscale', 'grayscale']
POST_AMOUNT = 100
COUNT = 100 #Number of images the search returned. Booru classes below were modified to update this value with the latest search result count.
DEBUG = False
RATING_TYPES = {
    "none": {
        "All": "All"
    },
    "full": {
        "All": "All",
        "Safe": "safe",
        "Questionable": "questionable",
        "Explicit": "explicit"
    },
    "single": {
        "All": "All",
        "Safe": "g",
        "Sensitive": "s",
        "Questionable": "q",
        "Explicit": "e"
    }
}
RATINGS = {
    "e621": RATING_TYPES['full'],
    "danbooru": RATING_TYPES['single'],
    "aibooru": RATING_TYPES['full'],
    "yande.re": RATING_TYPES['full'],
    "konachan": RATING_TYPES['full'],
    "safebooru": RATING_TYPES['none'],
    "rule34": RATING_TYPES['full'],
    "xbooru": RATING_TYPES['full'],
    "gelbooru": RATING_TYPES['single']
}


def get_available_ratings(booru):
    mature_ratings = gr.Radio.update(choices=RATINGS[booru].keys(), value="All")
    return mature_ratings


def show_fringe_benefits(booru):
    if booru == 'gelbooru':
        return gr.Checkbox.update(visible=True)
    else:
        return gr.Checkbox.update(visible=False)


def check_exception(booru, parameters):
    post_id = parameters.get('post_id')
    tags = parameters.get('tags')
    if booru == 'konachan' and post_id:
        raise Exception("Konachan does not support post IDs")
    if booru == 'yande.re' and post_id:
        raise Exception("Yande.re does not support post IDs")
    if booru == 'e621' and post_id:
        raise Exception("e621 does not support post IDs")
    if booru == 'danbooru' and tags and len(tags.split(',')) > 1: # Added tags check
        raise Exception("Danbooru does not support multiple tags. You can have only one tag.")


class Booru():

    def __init__(self, booru, booru_url):
        self.booru = booru
        self.booru_url = booru_url
        self.headers = {'user-agent': 'my-app/0.0.1'}

    def get_data(self, add_tags, max_pages=10, id=''):
        pass

    def get_post(self, add_tags, max_pages=10, id=''):
        pass


class Gelbooru(Booru):

    def __init__(self, fringe_benefits):
        super().__init__('gelbooru', f'https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}')
        self.fringeBenefits = fringe_benefits

    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT
        loop_msg = True
        for loop in range(2):
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&pid={random.randint(0, max_pages-1)}{id}{add_tags}"
            if self.fringeBenefits:
                res = requests.get(self.booru_url, cookies={'fringeBenefits': 'yup'})
            else:
                res = requests.get(self.booru_url)
            data = res.json()
            COUNT = data['@attributes']['count']
            if COUNT <= max_pages*POST_AMOUNT:
                max_pages = COUNT // POST_AMOUNT+1
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f" Processing {max_pages*POST_AMOUNT} out of {COUNT} results.")
            break
        return data

    def get_post(self, add_tags, max_pages=10, id=''):
        return self.get_data(add_tags, max_pages, "&id=" + id)


class XBooru(Booru):

    def __init__(self):
        super().__init__('xbooru', f'https://xbooru.com/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}')

    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT
        loop_msg = True
        for loop in range(2):
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&pid={random.randint(0, max_pages-1)}{id}{add_tags}"
            print(self.booru_url)
            res = requests.get(self.booru_url)
            data = res.json()
            COUNT = 0
            for post in data:
                post['file_url'] = f"https://xbooru.com/images/{post['directory']}/{post['image']}"
                COUNT += 1
            if COUNT <= max_pages*POST_AMOUNT:
                max_pages = COUNT // POST_AMOUNT+1
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f" Processing {max_pages*POST_AMOUNT} out of {COUNT} results.")
            break
        return {'post': data}

    def get_post(self, add_tags, max_pages=10, id=''):
        return self.get_data(add_tags, max_pages, "&id=" + id)


class Rule34(Booru):

    def __init__(self):
        super().__init__('rule34', f'https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}')

    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT
        loop_msg = True
        for loop in range(2):
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&pid={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)
            data = res.json()
            COUNT = len(data)
            if COUNT == 0:
                max_pages = 2
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f"Found enough results")
            break
        return {'post': data}

    def get_post(self, add_tags, max_pages=10, id=''):
        return self.get_data(add_tags, max_pages, "&id=" + id)


class Safebooru(Booru):

    def __init__(self):
        super().__init__('safebooru', f'https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}')

    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT
        loop_msg = True
        for loop in range(2):
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&pid={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)
            data = res.json()
            COUNT = 0
            for post in data:
                post['file_url'] = f"https://safebooru.org/images/{post['directory']}/{post['image']}"
                COUNT += 1
            if COUNT <= max_pages*POST_AMOUNT:
                max_pages = COUNT // POST_AMOUNT+1
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f" Processing {max_pages*POST_AMOUNT} out of {COUNT} results.")
            break
        return {'post': data}

    def get_post(self, add_tags, max_pages=10, id=''):
        return self.get_data(add_tags, max_pages, "&id=" + id)


class Konachan(Booru):

    def __init__(self):
        super().__init__('konachan', f'https://konachan.com/post.json?limit={POST_AMOUNT}')

    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT
        loop_msg = True
        for loop in range(2):
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&page={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)
            data = res.json()
            COUNT = len(data)
            if COUNT == 0:
                max_pages = 2
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f"Found enough results")
            break
        return {'post': data}

    def get_post(self, add_tags, max_pages=10, id=''):
        raise Exception("Konachan does not support post IDs")


class Yandere(Booru):

    def __init__(self):
        super().__init__('yande.re', f'https://yande.re/post.json?limit={POST_AMOUNT}')

    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT
        loop_msg = True
        for loop in range(2):
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&page={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)
            data = res.json()
            COUNT = len(data)
            if COUNT == 0: # Fixed duplicate COUNT = len(data)
                max_pages = 2
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f"Found enough results")
            break
        return {'post': data}

    def get_post(self, add_tags, max_pages=10, id=''):
        raise Exception("Yande.re does not support post IDs")


class AIBooru(Booru):

    def __init__(self):
        super().__init__('AIBooru', f'https://aibooru.online/posts.json?limit={POST_AMOUNT}') # Corrected class name in super

    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT
        loop_msg = True
        for loop in range(2):
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&page={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)
            data = res.json()
            for post in data:
                post['tags'] = post['tag_string']
            COUNT = len(data)
            if COUNT == 0:
                max_pages = 2
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f"Found enough results")
            break
        return {'post': data}

    def get_post(self, add_tags, max_pages=10, id=''):
        raise Exception("AIBooru does not support post IDs")


class Danbooru(Booru):

    def __init__(self):
        super().__init__('danbooru', f'https://danbooru.donmai.us/posts.json?limit={POST_AMOUNT}')

    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT
        loop_msg = True
        for loop in range(2):
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&page={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url, headers=self.headers)
            data = res.json()
            for post in data:
                post['tags'] = post['tag_string']
            COUNT = len(data)
            if COUNT == 0:
                max_pages = 2
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f"Found enough results")
            break
        return {'post': data}

    def get_post(self, add_tags, max_pages=10, id=''): # Unindented this method
        self.booru_url = f"https://danbooru.donmai.us/posts/{id}.json"
        res = requests.get(self.booru_url, headers=self.headers)
        data = res.json()
        data['tags'] = data['tag_string']
        data = {'post': [data]} # Wrapped in 'post' list
        return data


class e621(Booru): # Corrected class name from 'e621' to 'e621' if it was 'danbooru' by mistake in original

    def __init__(self):
        super().__init__('e621', f'https://e621.net/posts.json?limit={POST_AMOUNT}') # Corrected super call

    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT
        loop_msg = True
        for loop in range(2):
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&page={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url, headers=self.headers)
            data_res = res.json() # Store result
            data = data_res.get('posts', []) # Safely get 'posts'
            COUNT = len(data)
            for post in data: # Iterate over 'data' which is list of posts
                temp_tags = []
                sublevels = ['general', 'artist', 'copyright', 'character', 'species']
                for sublevel in sublevels:
                    temp_tags.extend(post.get('tags', {}).get(sublevel, [])) # Safe access
                post['tags'] = ' '.join(temp_tags)
                post['score'] = post.get('score', {}).get('total', 0) # Safe access
            if COUNT <= max_pages*POST_AMOUNT: # Logic seems okay
                max_pages = (COUNT // POST_AMOUNT) + 1 if COUNT > 0 else 1 # Avoid division by zero if COUNT is 0
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f" Processing {max_pages*POST_AMOUNT} out of {COUNT} results.")
            break
        return {'post': data} # Return in expected format

    def get_post(self, add_tags, max_pages=10, id=''): # Unindented
        # This method was likely meant to fetch a single post by ID for e621
        # The original was "self.get_data(add_tags, max_pages, "&id=" + id)" which might not be correct for e621's single post endpoint
        # Assuming a similar structure to Danbooru.get_post for fetching a single post
        self.booru_url = f"https://e621.net/posts/{id}.json"
        res = requests.get(self.booru_url, headers=self.headers)
        data = res.json().get('post', {}) # Safely get 'post'
        if not data: # If post is empty or not found
             return {'post': []} # Return empty list in expected structure
        temp_tags = []
        sublevels = ['general', 'artist', 'copyright', 'character', 'species']
        for sublevel in sublevels:
            temp_tags.extend(data.get('tags', {}).get(sublevel, []))
        data['tags'] = ' '.join(temp_tags)
        data['score'] = data.get('score', {}).get('total', 0)
        return {'post': [data]} # Wrap in list


def generate_chaos(pos_tags, neg_tags, chaos_amount):
    chaos_list = [tag for tag in pos_tags.split(',') + neg_tags.split(',') if tag.strip() != '']
    chaos_list = list(set(chaos_list))
    random.shuffle(chaos_list)
    len_list = round(len(chaos_list) * chaos_amount)
    pos_list = chaos_list[len_list:]
    pos_prompt = ','.join(pos_list)
    neg_list = chaos_list[:len_list]
    random.shuffle(neg_list)
    neg_prompt = ','.join(neg_list)
    return pos_prompt, neg_prompt


def resize_image(img, width, height, cropping=True):
    if cropping:
        x, y = img.size
        if x < y:
            wpercent = (width / float(img.size[0]))
            hsize = int((float(img.size[1]) * float(wpercent)))
            img_new = img.resize((width, hsize))
            if img_new.size[1] < height:
                hpercent = (height / float(img.size[1]))
                wsize = int((float(img.size[0]) * float(hpercent)))
                img_new = img.resize((wsize, height))
        else:
            ypercent = (height / float(img.size[1]))
            wsize = int((float(img.size[0]) * float(ypercent)))
            img_new = img.resize((wsize, height))
            if img_new.size[0] < width:
                xpercent = (width / float(img.size[0]))
                hsize = int((float(img.size[1]) * float(xpercent)))
                img_new = img.resize((width, hsize))
        x, y = img_new.size
        left = (x - width) / 2
        top = (y - height) / 2
        right = (x + width) / 2
        bottom = (y + height) / 2
        img = img_new.crop((left, top, right, bottom))
    else:
        img = img.resize((width, height))
    return img

def modify_prompt(prompt, tagged_prompt, type_deepbooru):
    if type_deepbooru == 'Add Before':
        return tagged_prompt + ',' + prompt
    elif type_deepbooru == 'Add After':
        return prompt + ',' + tagged_prompt
    elif type_deepbooru == 'Replace':
        return tagged_prompt
    return prompt

def remove_repeated_tags(prompt):
    prompt = prompt.split(',')
    new_prompt = []
    for tag in prompt:
        if tag not in new_prompt:
            new_prompt.append(tag)
    return ','.join(new_prompt)

def limit_prompt_tags(prompt, limit_tags, mode):
    clean_prompt = prompt.split(',')
    if mode == 'Limit':
        clean_prompt = clean_prompt[:int(len(clean_prompt) * limit_tags)]
    elif mode == 'Max':
        clean_prompt = clean_prompt[:limit_tags]
    return ','.join(clean_prompt)

class Script(scripts.Script):
    previous_loras = ''
    last_img = []
    real_steps = 0
    version = "1.2"
    original_prompt = ''

    def process_wildcards(self, current_tags_string):
        import re
        import os
        import random

        processed_tags = current_tags_string

        while True:
            match = re.search(r'__([a-zA-Z0-9_]+)__', processed_tags)
            if not match:
                break

            keyword = match.group(1)
            wildcard_to_replace = match.group(0)

            replacement_tag = ""

            # Uses the global 'user_wildcards_dir' defined at the top of the script
            file_path = os.path.join(user_wildcards_dir, f"{keyword}.txt")

            if os.path.exists(file_path) and os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        possible_tags = [line.strip() for line in f if line.strip()]
                    if possible_tags:
                        replacement_tag = random.choice(possible_tags)
                except Exception as e:
                    print(f"[Ranbooru] Error reading wildcard file {file_path}: {e}")

            processed_tags = processed_tags.replace(wildcard_to_replace, replacement_tag, 1)

        final_tags_list = [tag.strip() for tag in processed_tags.split(',') if tag.strip()]
        return ','.join(final_tags_list)

    def get_files(self, path):
        files = []
        for file in os.listdir(path):
            if file.endswith('.txt'):
                files.append(file)
        return files

    def hide_object(self, obj, booru):
        print(f'hide_object: {obj}, {booru.value}')
        if booru.value == 'konachan' or booru.value == 'yande.re':
            obj.interactive = False
        else:
            obj.interactive = True

    def title(self):
        return "Ranbooru"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def refresh_ser(self):
        return gr.update(choices=self.get_files(user_search_dir))
    def refresh_rem(self):
        return gr.update(choices=self.get_files(user_remove_dir))

    def get_forbidden_files(self):
        os.makedirs(user_forbidden_prompt_dir, exist_ok=True)
        files = [f for f in os.listdir(user_forbidden_prompt_dir) if f.endswith('.txt')]
        if not files and not os.path.exists(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt')):
            with open(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt'), 'w') as f:
                f.write("# Add tags here, one per line\n")
                f.write("artist_name_example\n")
                f.write("character_name_example\n")
            files.append('tags_forbidden.txt')
        elif 'tags_forbidden.txt' not in files and not os.path.exists(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt')):
             with open(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt'), 'w') as f:
                f.write("# Add tags here, one per line\n")
                f.write("artist_name_example\n")
                f.write("character_name_example\n")
        if 'tags_forbidden.txt' not in files and os.path.exists(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt')):
            files.append('tags_forbidden.txt')
        return files if files else ['tags_forbidden.txt']

    def refresh_forbidden_files(self):
        return gr.update(choices=self.get_forbidden_files())

    def ui(self, is_img2img):
        with InputAccordion(False, label="Ranbooru", elem_id=self.elem_id("ra_enable")) as enabled:
            booru = gr.Dropdown(
                ["gelbooru", "rule34", "safebooru", "danbooru", "konachan", 'yande.re', 'aibooru', 'xbooru', 'e621'], label="Booru", value="gelbooru")
            max_pages = gr.Slider(label="Max Pages", minimum=1, maximum=100, value=100, step=1)
            gr.Markdown("""## Post""")
            post_id = gr.Textbox(lines=1, label="Post ID")
            gr.Markdown("""## Tags""")
            tags = gr.Textbox(lines=1, label="Tags to Search (Pre)", info="Use __wildcard__ to pick a random tag from user/wildcards/wildcard.txt")
            remove_tags = gr.Textbox(lines=1, label="Tags to Remove (Post)")
            mature_rating = gr.Radio(list(RATINGS['gelbooru']), label="Mature Rating", value="All")
            remove_bad_tags = gr.Checkbox(label="Remove bad tags", value=True)
            shuffle_tags = gr.Checkbox(label="Shuffle tags", value=True)
            change_dash = gr.Checkbox(label='Convert "_" to spaces', value=False)
            same_prompt = gr.Checkbox(label="Use same prompt for all images", value=False)
            fringe_benefits = gr.Checkbox(label="Fringe Benefits", value=True)
            limit_tags = gr.Slider(value=1.0, label="Limit tags", minimum=0.05, maximum=1.0, step=0.05)
            max_tags = gr.Slider(value=100, label="Max tags", minimum=1, maximum=100, step=1)
            change_background = gr.Radio(["Don't Change", "Add Background", "Remove Background", "Remove All"], label="Change Background", value="Don't Change")
            change_color = gr.Radio(["Don't Change", "Colored", "Limited Palette", "Monochrome"], label="Change Color", value="Don't Change")
            sorting_order = gr.Radio(["Random", "High Score", "Low Score"], label="Sorting Order", value="Random")
            disable_prompt_modification = gr.Checkbox(label="Disable Ranbooru prompt modification", value=False)

            booru.change(get_available_ratings, booru, mature_rating)
            booru.change(show_fringe_benefits, booru, fringe_benefits)

            gr.Markdown("""\n---\n""")
            gr.Markdown("### Post-Fetch Prompt Tag Filtering")
            forbidden_prompt_tags_text = gr.Textbox(lines=2, label="Forbidden Prompt Tags (Manual Input)", info="Comma-separated. Tags to remove from prompt AFTER image selection.")
            use_forbidden_prompt_txt = gr.Checkbox(label="Use Forbidden Prompt Tags from file", value=False)
            choose_forbidden_prompt_txt = gr.Dropdown(self.get_forbidden_files(), label="Choose Forbidden Prompt Tags .txt file", value="tags_forbidden.txt")
            forbidden_refresh_btn = gr.Button("Refresh Forbidden Files")
            gr.Markdown("""\n---\n""")
            with gr.Group():
                with gr.Accordion("Img2Img", open=False):
                    use_img2img = gr.Checkbox(label="Use img2img", value=False)
                    use_ip = gr.Checkbox(label="Send to Controlnet", value=False)
                    denoising = gr.Slider(value=0.75, label="Denoising", minimum=0.05, maximum=1.0, step=0.05)
                    use_last_img = gr.Checkbox(label="Use last image as img2img", value=False)
                    crop_center = gr.Checkbox(label="Crop Center", value=False)
                    use_deepbooru = gr.Checkbox(label="Use Deepbooru", value=False)
                    type_deepbooru = gr.Radio(["Add Before", "Add After", "Replace"], label="Deepbooru Tags Position", value="Add Before")
            with gr.Group():
                with gr.Accordion("File", open=False):
                    use_search_txt = gr.Checkbox(label="Use tags_search.txt", value=False)
                    choose_search_txt = gr.Dropdown(self.get_files(user_search_dir), label="Choose tags_search.txt", value="")
                    search_refresh_btn = gr.Button("Refresh")
                    use_remove_txt = gr.Checkbox(label="Use tags_remove.txt", value=False)
                    choose_remove_txt = gr.Dropdown(self.get_files(user_remove_dir), label="Choose tags_remove.txt", value="")
                    remove_refresh_btn = gr.Button("Refresh")
            with gr.Group():
                with gr.Accordion("Extra", open=False):
                    with gr.Box():
                        mix_prompt = gr.Checkbox(label="Mix prompts", value=False)
                        mix_amount = gr.Slider(value=2, label="Mix amount", minimum=2, maximum=10, step=1)
                    with gr.Box():
                        chaos_mode = gr.Radio(["None", "Chaos", "Less Chaos"], label="Chaos Mode", value="None")
                        chaos_amount = gr.Slider(value=0.5, label="Chaos Amount %", minimum=0.1, maximum=1, step=0.05)
                    with gr.Box():
                        negative_mode = gr.Radio(["None", "Negative"], label="Negative Mode", value="None")
                        use_same_seed = gr.Checkbox(label="Use same seed for all pictures", value=False)
                    with gr.Box():
                        use_cache = gr.Checkbox(label="Use cache", value=True)
        with InputAccordion(False, label="LoRAnado", elem_id=self.elem_id("lo_enable")) as lora_enabled:
            with gr.Box():
                lora_lock_prev = gr.Checkbox(label="Lock previous LoRAs", value=False)
                lora_folder = gr.Textbox(lines=1, label="LoRAs Subfolder")
                lora_amount = gr.Slider(value=1, label="LoRAs Amount", minimum=1, maximum=10, step=1)
            with gr.Box():
                lora_min = gr.Slider(value=-1.0, label="Min LoRAs Weight", minimum=-1.0, maximum=1, step=0.1)
                lora_max = gr.Slider(value=1.0, label="Max LoRAs Weight", minimum=-1.0, maximum=1.0, step=0.1)
                lora_custom_weights = gr.Textbox(lines=1, label="LoRAs Custom Weights")

        search_refresh_btn.click(fn=self.refresh_ser, inputs=[], outputs=[choose_search_txt])
        remove_refresh_btn.click(fn=self.refresh_rem, inputs=[], outputs=[choose_remove_txt])
        forbidden_refresh_btn.click(fn=self.refresh_forbidden_files, inputs=[], outputs=[choose_forbidden_prompt_txt])

        return [enabled, tags, booru, remove_bad_tags, max_pages, change_dash, same_prompt, fringe_benefits, remove_tags, use_img2img, denoising, use_last_img, change_background, change_color, shuffle_tags, post_id, mix_prompt, mix_amount, chaos_mode, negative_mode, chaos_amount, limit_tags, max_tags, sorting_order, mature_rating, lora_folder, lora_amount, lora_min, lora_max, lora_enabled, lora_custom_weights, lora_lock_prev, use_ip, use_search_txt, use_remove_txt, choose_search_txt, choose_remove_txt, search_refresh_btn, remove_refresh_btn, forbidden_prompt_tags_text, use_forbidden_prompt_txt, choose_forbidden_prompt_txt, crop_center, use_deepbooru, type_deepbooru, use_same_seed, use_cache, disable_prompt_modification]

    def check_orientation(self, img):
        x, y = img.size
        if x / y > 1.2: return [768, 512]
        elif y / x > 1.2: return [512, 768]
        else: return [768, 768]

    def loranado(self, lora_enabled, lora_folder, lora_amount, lora_min, lora_max, lora_custom_weights, p, lora_lock_prev):
        lora_prompt = ''
        if lora_enabled:
            if lora_lock_prev:
                lora_prompt = self.previous_loras
            else:
                loras = os.listdir(f'{lora_folder}')
                loras = [lora.replace('.safetensors', '') for lora in loras if lora.endswith('.safetensors')]
                for l in range(0, lora_amount):
                    lora_weight = 0
                    if lora_custom_weights != '':
                        lora_weight = float(lora_custom_weights.split(',')[l])
                    while lora_weight == 0:
                        lora_weight = round(random.uniform(lora_min, lora_max), 1)
                    lora_prompt += f'<lora:{random.choice(loras)}:{lora_weight}>'
                self.previous_loras = lora_prompt
        if lora_prompt:
            if isinstance(p.prompt, list):
                for num, pr in enumerate(p.prompt): p.prompt[num] = f'{lora_prompt} {pr}'
            else: p.prompt = f'{lora_prompt} {p.prompt}'
        return p

    def before_process(self, p, enabled, tags, booru, remove_bad_tags, max_pages, change_dash, same_prompt, fringe_benefits, remove_tags, use_img2img, denoising, use_last_img, change_background, change_color, shuffle_tags, post_id, mix_prompt, mix_amount, chaos_mode, negative_mode, chaos_amount, limit_tags, max_tags, sorting_order, mature_rating, lora_folder, lora_amount, lora_min, lora_max, lora_enabled, lora_custom_weights, lora_lock_prev, use_ip, use_search_txt, use_remove_txt, choose_search_txt, choose_remove_txt, search_refresh_btn, remove_refresh_btn, forbidden_prompt_tags_text, use_forbidden_prompt_txt, choose_forbidden_prompt_txt, crop_center, use_deepbooru, type_deepbooru, use_same_seed, use_cache, disable_prompt_modification):
        if use_cache and not requests_cache.patcher.is_installed(): requests_cache.install_cache('ranbooru_cache', backend='sqlite', expire_after=3600)
        elif not use_cache and requests_cache.patcher.is_installed(): requests_cache.uninstall_cache()
        if enabled:
            if disable_prompt_modification:
                if lora_enabled: p = self.loranado(lora_enabled, lora_folder, lora_amount, lora_min, lora_max, lora_custom_weights, p, lora_lock_prev)
                return

            booru_apis = {
                'gelbooru': Gelbooru(fringe_benefits), 'rule34': Rule34(), 'safebooru': Safebooru(),
                'danbooru': Danbooru(), 'konachan': Konachan(), 'yande.re': Yandere(),
                'aibooru': AIBooru(), 'xbooru': XBooru(), 'e621': e621(),
            }
            self.original_prompt = p.prompt
            tags = self.process_wildcards(tags)
            check_exception(booru, {'tags': tags, 'post_id': post_id})
            # ... (rest of before_process method as it was, assuming it's largely correct)
            bad_tags = []
            if remove_bad_tags: bad_tags = ['mixed-language_text', 'watermark', 'text', 'english_text', 'speech_bubble', 'signature', 'artist_name', 'censored', 'bar_censor', 'translation', 'twitter_username', "twitter_logo", 'patreon_username', 'commentary_request', 'tagme', 'commentary', 'character_name', 'mosaic_censoring', 'instagram_username', 'text_focus', 'english_commentary', 'comic', 'translation_request', 'fake_text', 'translated', 'paid_reward_available', 'thought_bubble', 'multiple_views', 'silent_comic', 'out-of-frame_censoring', 'symbol-only_commentary', '3koma', '2koma', 'character_watermark', 'spoken_question_mark', 'japanese_text', 'spanish_text', 'language_text', 'fanbox_username', 'commission', 'original', 'ai_generated', 'stable_diffusion', 'tagme_(artist)', 'text_bubble', 'qr_code', 'chinese_commentary', 'korean_text', 'partial_commentary', 'chinese_text', 'copyright_request', 'heart_censor', 'censored_nipples', 'page_number', 'scan', 'fake_magazine_cover', 'korean_commentary']
            if ',' in remove_tags: bad_tags.extend(remove_tags.split(','))
            else: bad_tags.append(remove_tags)
            if use_remove_txt: bad_tags.extend(open(os.path.join(user_remove_dir, choose_remove_txt), 'r').read().split(','))
            background_options = {'Add Background': ('detailed_background,' + random.choice(["outdoors", "indoors"]), COLORED_BG), 'Remove Background': ('plain_background,simple_background,' + random.choice(COLORED_BG), ADD_BG), 'Remove All': ('', COLORED_BG + ADD_BG)}
            if change_background in background_options:
                prompt_addition, tags_to_remove = background_options[change_background]
                bad_tags.extend(tags_to_remove)
                p.prompt = f'{p.prompt},{prompt_addition}' if p.prompt else prompt_addition
            color_options = {'Colored': BW_BG, 'Limited Palette': '(limited_palette:1.3)', 'Monochrome': ','.join(BW_BG)}
            if change_color in color_options:
                color_option = color_options[change_color]
                if isinstance(color_option, list): bad_tags.extend(color_option)
                else: p.prompt = f'{p.prompt},{color_option}' if p.prompt else color_option
            if use_search_txt:
                search_tags_content = open(os.path.join(user_search_dir, choose_search_txt), 'r').read() # Renamed variable
                search_tags_r = search_tags_content.replace(" ", "")
                split_tags = search_tags_r.splitlines()
                filtered_tags = [line for line in split_tags if line.strip()]
                if filtered_tags:
                    selected_tags = random.choice(filtered_tags) # Simplified random choice
                    tags = f'{tags},{selected_tags}' if tags else selected_tags
            add_tags_query = '&tags=-animated' # Renamed variable
            if tags:
                add_tags_query += f'+{tags.replace(",", "+")}'
                if mature_rating != 'All': add_tags_query += f'+rating:{RATINGS[booru][mature_rating]}'
            random_post = {'preview_url': ''}
            prompts = []
            global last_img # Ensure it's treated as global if modified here
            last_img = []
            preview_urls = []
            api_url = booru_apis.get(booru, Gelbooru(fringe_benefits))
            print(f'Using {booru}')
            if post_id: data = api_url.get_post(add_tags_query, max_pages, post_id)
            else: data = api_url.get_data(add_tags_query, max_pages)
            print(api_url.booru_url)
            if 'post' not in data and 'posts' in data : data['post'] = data['posts'] # Compatibility for e621 like structure
            if 'post' not in data or not data['post']: data['post'] = [] # Ensure data['post'] is a list
            for post_item in data['post']: post_item['score'] = post_item.get('score', 0) # Renamed post to post_item
            if sorting_order == 'High Score': data['post'] = sorted(data['post'], key=lambda k: k.get('score', 0), reverse=True)
            elif sorting_order == 'Low Score': data['post'] = sorted(data['post'], key=lambda k: k.get('score', 0))
            random_numbers = [0 for _ in range(0, p.batch_size * p.n_iter)] if post_id else self.random_number(sorting_order, p.batch_size * p.n_iter)
            for random_number in random_numbers:
                current_random_post = data['post'][random_numbers[0] if same_prompt else random_number] # Renamed
                if mix_prompt and not same_prompt : # mix_prompt only if not same_prompt
                    temp_tags_mix = [] # Renamed
                    max_tags_mix = 0 # Renamed
                    for _ in range(0, mix_amount):
                        random_mix_number = self.random_number(sorting_order, 1)[0] if not post_id else 0
                        temp_tags_mix.extend(data['post'][random_mix_number]['tags'].split(' '))
                        max_tags_mix = max(max_tags_mix, len(data['post'][random_mix_number]['tags'].split(' ')))
                    temp_tags_mix = list(set(temp_tags_mix))
                    current_random_post = data['post'][random_number] # Already defined, this line is redundant?
                    max_tags_mix = min(max(len(temp_tags_mix), 20), max_tags_mix) # max_tags was used before, changed to max_tags_mix
                    current_random_post['tags'] = ' '.join(random.sample(temp_tags_mix, max_tags_mix))
                else: # if not mix_prompt or same_prompt
                     current_random_post = data['post'][random_number if not same_prompt else random_numbers[0]]
                clean_tags = current_random_post.get('tags', '').replace('(', r'\(').replace(')', r'\)') # Added .get
                temp_tags_list = random.sample(clean_tags.split(' '), len(clean_tags.split(' '))) if shuffle_tags and clean_tags else clean_tags.split(' ') # Added clean_tags check
                prompts.append(','.join(temp_tags_list))
                preview_urls.append(current_random_post.get('file_url', 'https://pic.re/image'))
            if use_img2img or use_deepbooru:
                image_urls = [data['post'][random_numbers[0]]['file_url']] if use_last_img and data['post'] else preview_urls # Added data['post'] check
                for img_url in image_urls: # Renamed img to img_url
                    response = requests.get(img_url, headers=api_url.headers)
                    last_img.append(Image.open(BytesIO(response.content)))
            new_prompts = []
            for current_prompt in prompts: # Renamed prompt to current_prompt
                prompt_tags_list = [tag for tag in html.unescape(current_prompt).split(',') if tag.strip() not in bad_tags]
                for bad_tag_item in bad_tags: # Renamed bad_tag to bad_tag_item
                    if '*' in bad_tag_item: prompt_tags_list = [tag for tag in prompt_tags_list if bad_tag_item.replace('*', '') not in tag]
                new_prompt_str = ','.join(prompt_tags_list) # Renamed
                if change_dash: new_prompt_str = new_prompt_str.replace("_", " ")
                new_prompts.append(new_prompt_str)
            prompts = new_prompts
            if len(prompts) == 1:
                ranbooru_tags_to_add = prompts[0]
                current_prompt_content = p.prompt.strip() if isinstance(p.prompt, str) else "" # Handle p.prompt list case
                if current_prompt_content and ranbooru_tags_to_add: p.prompt = f"{current_prompt_content},{ranbooru_tags_to_add}"
                elif ranbooru_tags_to_add: p.prompt = ranbooru_tags_to_add
                if chaos_mode in ['Chaos', 'Less Chaos']:
                    base_neg_for_chaos = p.negative_prompt if chaos_mode == 'Chaos' else ''
                    p.prompt, generated_chaos_neg_tags = generate_chaos(p.prompt, base_neg_for_chaos, chaos_amount)
                    if p.negative_prompt and generated_chaos_neg_tags: p.negative_prompt = f"{p.negative_prompt},{generated_chaos_neg_tags}"
                    elif generated_chaos_neg_tags: p.negative_prompt = generated_chaos_neg_tags
            else: # len(prompts) > 1
                base_neg_prompt_from_ui = p.negative_prompt
                if chaos_mode == 'Chaos':
                    # ... (rest of chaos logic largely similar, ensure variables are defined)
                    new_positive_prompts_list = []
                    new_negative_prompts_list = []
                    for ran_prompt_item in prompts:
                        tmp_pos, tmp_neg = generate_chaos(ran_prompt_item, base_neg_prompt_from_ui, chaos_amount)
                        new_positive_prompts_list.append(tmp_pos)
                        new_negative_prompts_list.append(tmp_neg)
                    prompts = new_positive_prompts_list
                    p.negative_prompt = new_negative_prompts_list
                elif chaos_mode == 'Less Chaos':
                    new_positive_prompts_list = []
                    new_negative_prompts_list = []
                    for ran_prompt_item in prompts:
                        tmp_pos, tmp_neg_chaos_only = generate_chaos(ran_prompt_item, "", chaos_amount)
                        new_positive_prompts_list.append(tmp_pos)
                        current_neg = f"{base_neg_prompt_from_ui},{tmp_neg_chaos_only}" if base_neg_prompt_from_ui and tmp_neg_chaos_only else (base_neg_prompt_from_ui or tmp_neg_chaos_only or "")
                        new_negative_prompts_list.append(current_neg)
                    prompts = new_positive_prompts_list
                    p.negative_prompt = new_negative_prompts_list
                else:
                    p.negative_prompt = [base_neg_prompt_from_ui for _ in range(len(prompts))]
                base_prompt_from_ui = self.original_prompt.strip()
                processed_prompts_list = []
                for ran_prompt_item in prompts:
                    if base_prompt_from_ui and ran_prompt_item: processed_prompts_list.append(f"{base_prompt_from_ui},{ran_prompt_item}")
                    elif ran_prompt_item: processed_prompts_list.append(ran_prompt_item)
                    else: processed_prompts_list.append(base_prompt_from_ui)
                p.prompt = processed_prompts_list
                if use_img2img:
                    if len(last_img) < len(prompts): last_img = [last_img[0] for _ in range(len(prompts))] if last_img else []
            final_forbidden_tags = set()
            if forbidden_prompt_tags_text:
                manual_forbidden = [tag.strip().lower() for tag in forbidden_prompt_tags_text.split(',') if tag.strip()]
                final_forbidden_tags.update(manual_forbidden)
            if use_forbidden_prompt_txt and choose_forbidden_prompt_txt:
                forbidden_file_path = os.path.join(user_forbidden_prompt_dir, choose_forbidden_prompt_txt)
                if os.path.exists(forbidden_file_path):
                    try:
                        with open(forbidden_file_path, 'r', encoding='utf-8') as f:
                            file_forbidden = [line.strip().lower() for line in f if line.strip()]
                        final_forbidden_tags.update(file_forbidden)
                    except Exception as e: print(f"Error reading forbidden tags file {forbidden_file_path}: {e}")
            if final_forbidden_tags:
                if isinstance(p.prompt, list):
                    # ... (rest of forbidden tags filtering largely similar) ...
                    processed_prompts_forbidden = []
                    for current_prompt_str_forbidden in p.prompt:
                        prompt_tags_list_forbidden = [tag.strip() for tag in current_prompt_str_forbidden.split(',')]
                        kept_tags_forbidden = [tag for tag in prompt_tags_list_forbidden if tag.strip().lower() not in final_forbidden_tags]
                        processed_prompts_forbidden.append(','.join(kept_tags_forbidden))
                    p.prompt = processed_prompts_forbidden
                elif isinstance(p.prompt, str):
                    prompt_tags_list_forbidden = [tag.strip() for tag in p.prompt.split(',')]
                    kept_tags_forbidden = [tag for tag in prompt_tags_list_forbidden if tag.strip().lower() not in final_forbidden_tags]
                    p.prompt = ','.join(kept_tags_forbidden)
            if negative_mode == 'Negative':
                orig_list = self.original_prompt.split(',')
                if isinstance(p.prompt, list):
                    # ... (rest of negative mode largely similar) ...
                    new_positive_prompts_neg = []
                    new_negative_prompts_neg = []
                    for pr_neg, npp_neg in zip(p.prompt, p.negative_prompt if isinstance(p.negative_prompt, list) else [p.negative_prompt]*len(p.prompt)):
                        clean_prompt_neg = pr_neg.split(',')
                        clean_prompt_neg = [tag for tag in clean_prompt_neg if tag not in orig_list]
                        new_positive_prompts_neg.append(self.original_prompt)
                        new_negative_prompts_neg.append(f'{npp_neg},{",".join(clean_prompt_neg)}')
                    p.prompt = new_positive_prompts_neg
                    p.negative_prompt = new_negative_prompts_neg
                else:
                    clean_prompt_neg = p.prompt.split(',')
                    clean_prompt_neg = [tag for tag in clean_prompt_neg if tag not in orig_list]
                    p.negative_prompt = f'{p.negative_prompt},{",".join(clean_prompt_neg)}'
                    p.prompt = self.original_prompt
            if negative_mode == 'Negative' or chaos_mode in ['Chaos', 'Less Chaos']:
                if isinstance(p.negative_prompt, list): # Ensure it's a list before iterating
                    neg_prompt_tokens = [model_hijack.get_prompt_lengths(pr_item)[1] for pr_item in p.negative_prompt] # Renamed pr to pr_item
                    if len(set(neg_prompt_tokens)) != 1:
                        print('Padding negative prompts')
                        max_tokens = max(neg_prompt_tokens)
                        for num, neg_len in enumerate(neg_prompt_tokens): # Renamed neg to neg_len
                            while neg_len < max_tokens:
                                current_neg_prompt_item = p.negative_prompt[num].split(',') # Renamed
                                if current_neg_prompt_item : p.negative_prompt[num] += random.choice(current_neg_prompt_item)
                                else: p.negative_prompt[num] += "_" # Add padding if empty
                                neg_len = model_hijack.get_prompt_lengths(p.negative_prompt[num])[1]
            if limit_tags < 1:
                if isinstance(p.prompt, list): p.prompt = [limit_prompt_tags(pr_item, limit_tags, 'Limit') for pr_item in p.prompt]
                else: p.prompt = limit_prompt_tags(p.prompt, limit_tags, 'Limit')
            if max_tags > 0:
                if isinstance(p.prompt, list): p.prompt = [limit_prompt_tags(pr_item, max_tags, 'Max') for pr_item in p.prompt]
                else: p.prompt = limit_prompt_tags(p.prompt, max_tags, 'Max')
            if use_same_seed:
                p.seed = random.randint(0, 2 ** 32 - 1) if p.seed == -1 else p.seed
                if hasattr(p, 'batch_size') and p.batch_size is not None : p.seed = [p.seed] * p.batch_size
                else: p.seed = [p.seed] # if batch_size is not available or 1
            p = self.loranado(lora_enabled, lora_folder, lora_amount, lora_min, lora_max, lora_custom_weights, p, lora_lock_prev)
            if use_deepbooru and not use_img2img:
                self.last_img = last_img # ensure self.last_img is set
                tagged_prompts = self.use_autotagger('deepbooru')
                if isinstance(p.prompt, list):
                    p.prompt = [modify_prompt(pr_item, tagged_prompts[num], type_deepbooru) for num, pr_item in enumerate(p.prompt)]
                    p.prompt = [remove_repeated_tags(pr_item) for pr_item in p.prompt]
                else:
                    p.prompt = modify_prompt(p.prompt, tagged_prompts[0] if tagged_prompts else "", type_deepbooru) # Handle empty tagged_prompts
                    p.prompt = remove_repeated_tags(p.prompt)
            if use_img2img:
                if not use_ip:
                    self.real_steps = p.steps
                    p.steps = 1
                    self.last_img = last_img
                if use_ip:
                    controlNetModule = importlib.import_module('extensions.sd-webui-controlnet.scripts.external_code', 'external_code')
                    controlNetList = controlNetModule.get_all_units_in_processing(p)
                    if controlNetList: # Check if list is not empty
                        copied_network = controlNetList[0].__dict__.copy()
                        copied_network['enabled'] = True
                        copied_network['weight'] = denoising
                        if last_img: array_img = np.array(last_img[0]) # Check last_img not empty
                        else: array_img = np.zeros((512,512,3), dtype=np.uint8) # Dummy image if no image
                        copied_network['image']['image'] = array_img
                        copied_networks = [copied_network] + controlNetList[1:]
                        controlNetModule.update_cn_script_in_processing(p, copied_networks)
        elif lora_enabled:
            p = self.loranado(lora_enabled, lora_folder, lora_amount, lora_min, lora_max, lora_custom_weights, p, lora_lock_prev)

    def postprocess(self, p, processed, enabled, tags, booru, remove_bad_tags, max_pages, change_dash, same_prompt, fringe_benefits, remove_tags, use_img2img, denoising, use_last_img, change_background, change_color, shuffle_tags, post_id, mix_prompt, mix_amount, chaos_mode, negative_mode, chaos_amount, limit_tags, max_tags, sorting_order, mature_rating, lora_folder, lora_amount, lora_min, lora_max, lora_enabled, lora_custom_weights, lora_lock_prev, use_ip, use_search_txt, use_remove_txt, choose_search_txt, choose_remove_txt, search_refresh_btn, remove_refresh_btn, forbidden_prompt_tags_text, use_forbidden_prompt_txt, choose_forbidden_prompt_txt, crop_center, use_deepbooru, type_deepbooru, use_same_seed, use_cache, disable_prompt_modification):
        if use_img2img and not use_ip and enabled and self.last_img: # Added self.last_img check
            print('Using pictures')
            if crop_center:
                width, height = p.width, p.height
                self.last_img = [resize_image(img, width, height, cropping=True) for img in self.last_img]
            else:
                width, height = self.check_orientation(self.last_img[0])
            final_prompts = p.prompt
            if use_deepbooru:
                tagged_prompts = self.use_autotagger('deepbooru') # This returns a list
                if isinstance(p.prompt, list):
                    final_prompts = [modify_prompt(pr, (tagged_prompts[num] if num < len(tagged_prompts) else ""), type_deepbooru) for num, pr in enumerate(p.prompt)] # Check index
                    final_prompts = [remove_repeated_tags(pr) for pr in final_prompts]
                else: # p.prompt is a string
                    final_prompts = modify_prompt(p.prompt, (tagged_prompts[0] if tagged_prompts else ""), type_deepbooru) # Check index
                    final_prompts = remove_repeated_tags(final_prompts)

            # Ensure p.sampler_name and p.scheduler are valid, or provide defaults
            sampler_name = p.sampler_name if hasattr(p, 'sampler_name') and p.sampler_name else "Euler a"
            scheduler = p.scheduler if hasattr(p, 'scheduler') and p.scheduler else None

            p_img2img = StableDiffusionProcessingImg2Img( # Renamed variable
                sd_model=shared.sd_model,
                outpath_samples=shared.opts.outdir_samples or shared.opts.outdir_img2img_samples,
                outpath_grids=shared.opts.outdir_grids or shared.opts.outdir_img2img_grids,
                prompt=final_prompts,
                negative_prompt=p.negative_prompt,
                seed=p.seed,
                sampler_name=sampler_name, # Use ensured sampler_name
                scheduler=scheduler, # Use ensured scheduler
                batch_size=p.batch_size,
                n_iter=p.n_iter,
                steps=self.real_steps,
                cfg_scale=p.cfg_scale,
                width=width,
                height=height,
                init_images=self.last_img,
                denoising_strength=denoising,
            )
            proc = process_images(p_img2img) # Use new variable name
            processed.images = proc.images
            processed.infotexts = proc.infotexts
            if use_last_img:
                processed.images.append(self.last_img[0])
            else:
                for num, img in enumerate(self.last_img):
                    if num < len(proc.infotexts): # Ensure index exists
                         processed.images.append(img)
                         processed.infotexts.append(proc.infotexts[num]) # Corrected index for infotexts

    def random_number(self, sorting_order, size):
        global COUNT
        # Ensure COUNT is at least 1 to prevent error in np.arange or random.sample if size > COUNT
        effective_count = max(1, COUNT if COUNT <= POST_AMOUNT else POST_AMOUNT)
        if size > effective_count : size = effective_count # Cannot sample more than available

        if sorting_order in ('High Score', 'Low Score') and effective_count > 0: # effective_count > 0 for p value
            weights = np.arange(effective_count, 0, -1)
            weights = weights / weights.sum()
            # Ensure size is not greater than effective_count for choice with replace=False
            random_numbers = np.random.choice(np.arange(effective_count), size=min(size, effective_count), p=weights, replace=False)
        elif effective_count > 0 : # For random sort or if other conditions not met but count > 0
             random_numbers = random.sample(range(effective_count), min(size, effective_count))
        else: # effective_count is 0 or less (should be 1 due to max(1, ...))
            random_numbers = []
        return random_numbers.tolist() if isinstance(random_numbers, np.ndarray) else random_numbers


    def use_autotagger(self, model_name): # Renamed model to model_name
        if model_name == 'deepbooru' and self.last_img: # Added self.last_img check
            if isinstance(self.original_prompt, str):
                orig_prompt_list = [self.original_prompt] * len(self.last_img) # Match length of last_img
            elif isinstance(self.original_prompt, list):
                orig_prompt_list = self.original_prompt
                # Ensure orig_prompt_list length matches last_img, truncate or pad if necessary
                if len(orig_prompt_list) > len(self.last_img):
                    orig_prompt_list = orig_prompt_list[:len(self.last_img)]
                elif len(orig_prompt_list) < len(self.last_img):
                    orig_prompt_list.extend([orig_prompt_list[-1] if orig_prompt_list else ""] * (len(self.last_img) - len(orig_prompt_list)))
            else: # Fallback if original_prompt is not str or list
                orig_prompt_list = [""] * len(self.last_img)

            deepbooru.model.start()
            # Ensure that we iterate up to the minimum length of images and prompts available
            iter_len = min(len(self.last_img), len(orig_prompt_list))
            final_prompts = [orig_prompt_list[i] + ',' + deepbooru.model.tag_multi(self.last_img[i]) for i in range(iter_len)]
            deepbooru.model.stop()
            return final_prompts
        return [] # Return empty list if no processing done
