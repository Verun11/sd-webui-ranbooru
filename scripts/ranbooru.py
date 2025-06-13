from io import BytesIO
import html
import random
import requests
import modules.scripts as scripts
import gradio as gr
import os
from dotenv import load_dotenv
from PIL import Image
import numpy as np
import importlib
import requests_cache

from modules.processing import process_images, StableDiffusionProcessingImg2Img
from modules import shared
from modules.sd_hijack import model_hijack
from modules import deepbooru
from modules.ui_components import InputAccordion

load_dotenv()
extension_root = scripts.basedir()
user_data_dir = os.path.join(extension_root, 'user')
user_search_dir = os.path.join(user_data_dir, 'search')
user_remove_dir = os.path.join(user_data_dir, 'remove')
user_wildcards_dir = os.path.join(user_data_dir, 'wildcards')
user_forbidden_prompt_dir = os.path.join(user_data_dir, 'forbidden_prompt')
os.makedirs(user_search_dir, exist_ok=True)
os.makedirs(user_remove_dir, exist_ok=True)
os.makedirs(user_wildcards_dir, exist_ok=True)
os.makedirs(user_forbidden_prompt_dir, exist_ok=True)

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

GEL_API_AUTH, DAN_API_AUTH = '', ''
DANBOORU_TIER = os.getenv("danbooru_tier")
if os.getenv("danbooru_login") and os.getenv("danbooru_api_key"):
    DAN_API_AUTH = f'&login={os.getenv("danbooru_login")}&api_key={os.getenv("da\
nbooru_api_key")}'
if os.getenv("gelbooru_user_id") and os.getenv("gelbooru_api_key"):
    GEL_API_AUTH = f'&user_id={os.getenv("gelbooru_user_id")}&api_key={os.getenv\
("gelbooru_api_key")}'

COLORED_BG = ['black_background', 'aqua_background', 'white_background', 'colo\
red_background', 'gray_background', 'blue_background', 'green_background', 'red_ba\
ckground', 'brown_background', 'purple_background', 'yellow_background', 'orange\
_background', 'pink_background', 'plain', 'transparent_background', 'simple_back\
ground', 'two-tone_background', 'grey_background']
ADD_BG = ['outdoors', 'indoors']
BW_BG = ['monochrome', 'greyscale', 'grayscale']
POST_AMOUNT = 100
COUNT = 100 #Number of images the search returned. Booru classes below were modi\
fied to update this value with the latest search result count.
DEBUG = False
BOORU_ENDPOINTS= {
    "gelbooru": "https://gelbooru.com/index.php?page=post&s=view&id=",
    "rule34": "https://rule34.xxx/index.php?page=post&s=view&id=",
    "safebooru": "https://safebooru.org/index.php?page=post&s=view&id=",
    "danbooru": "https://danbooru.donmai.us/posts/",
    "konachan": "https://konachan.net/post/show/",
    "yande.re": "https://yande.re/post/show/",
    "aibooru": "https://aibooru.online/posts/",
    "xbooru": "https://xbooru.com/index.php?page=post&s=view&id=",
    "e621": "https://e621.net/posts/"
}

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
    "gelbooru": RATING_TYPES['full']
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
    if booru == 'danbooru' and len(tags.split(',')) > 1 and (DANBOORU_TIER is No\
ne or DANBOORU_TIER == 'member'):
        raise Exception("Danbooru does not support multiple tags. You can have o\
nly one tag.")


class Booru():

    def __init__(self, booru, booru_url):
        self.booru = booru
        self.booru_url = booru_url
        self.headers = {'user-agent': 'my-app/0.0.1'}

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''):
        pass

    def get_post(self, add_tags, max_pages=10, id=''):
        pass


class Gelbooru(Booru):

    def __init__(self, fringe_benefits):
        super().__init__('gelbooru', f'https://gelbooru.com/index.php?page=dapi&\
s=post&q=index&json=1&limit={POST_AMOUNT}{GEL_API_AUTH}')
        self.fringeBenefits = fringe_benefits

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''):
        global COUNT
        loop_msg = True # avoid showing same msg twice
        for loop in range(2): # run loop at most twice
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&pid={random.randint(0, max_pages-1)}{id}{add_tags}"
            # The randint function is an alias to randrange(a, b+1), so 'max_pages' should be passed as 'max_pages-1'
            if self.fringeBenefits:
                res = requests.get(self.booru_url, cookies={'fringeBenefits': 'yup'})
            else:
                res = requests.get(self.booru_url)
            data = res.json()
            COUNT = data['@attributes']['count']
            if COUNT <= max_pages*POST_AMOUNT:
                max_pages = COUNT // POST_AMOUNT+1
                # If max_pages is bigger than available pages, loop the function\
 with updated max_pages based on the value of COUNT
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                    # avoid showing same msg twice
                continue
            else:
                print(f" Processing {max_pages*POST_AMOUNT} out of {COUNT} resul\
ts.")
            break
        return data

    def get_post(self, add_tags, max_pages=10, id=''):
        return self.get_data(add_tags, user_tagged, max_pages, "&id=" + id)


class XBooru(Booru):

    def __init__(self):
        super().__init__('xbooru', f'https://xbooru.com/index.php?page=dapi&s=po\
st&q=index&json=1&limit={POST_AMOUNT}')

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''):
        global COUNT
        loop_msg = True # avoid showing same msg twice
        for loop in range(2): # run loop at most twice
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&pid={random.randint(0, max_pages\
-1)}{id}{add_tags}"
            print(self.booru_url)
            res = requests.get(self.booru_url)
            data = res.json()
            COUNT = 0
            for post in data:
                post['file_url'] = f"https://xbooru.com/images/{post['directory']\
}/{post['image']}"
                COUNT += 1
            if COUNT <= max_pages*POST_AMOUNT:
                max_pages = COUNT // POST_AMOUNT+1
                # If max_pages is bigger than available pages, loop the function\
 with updated max_pages based on the value of COUNT
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                    # avoid showing same msg twice
                continue
            else:
                print(f" Processing {max_pages*POST_AMOUNT} out of {COUNT} resul\
ts.")
            break
        return {'post': data}

    def get_post(self, add_tags, max_pages=10, id=''):
        return self.get_data(add_tags, user_tagged, max_pages, "&id=" + id)


class Rule34(Booru):

    def __init__(self):
        super().__init__('rule34', f'https://api.rule34.xxx/index.php?page=dapi&\
s=post&q=index&json=1&limit={POST_AMOUNT}')

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''):
        global COUNT
        loop_msg = True # avoid showing same msg twice
        for loop in range(2): # run loop at most twice
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&pid={random.randint(0, max_pages\
-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)
            data = res.json()
            COUNT = len(data)
            if COUNT == 0:
                max_pages = 2
                # Rule34 does not have a way to know the amount of results avail\
able in the search, so we need to run the function again with a fixed amount of \
pages
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                    # avoid showing same msg twice
                continue
            else:
                print(f"Found enough results")
            break
        return {'post': data}

    def get_post(self, add_tags, max_pages=10, id=''):
        return self.get_data(add_tags, user_tagged, max_pages, "&id=" + id)


class Safebooru(Booru):

    def __init__(self):
        super().__init__('safebooru', f'https://safebooru.org/index.php?page=dap\
i&s=post&q=index&json=1&limit={POST_AMOUNT}')

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''):
        global COUNT
        loop_msg = True # avoid showing same msg twice
        for loop in range(2): # run loop at most twice
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&pid={random.randint(0, max_pages\
-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)
            data = res.json()
            COUNT = 0
            for post in data:
                post['file_url'] = f"https://safebooru.org/images/{post['directo\
ry']}/{post['image']}"
                COUNT += 1
            if COUNT <= max_pages*POST_AMOUNT:
                max_pages = COUNT // POST_AMOUNT+1
                # If max_pages is bigger than available pages, loop the function\
 with updated max_pages based on the value of COUNT
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                    # avoid showing same msg twice
                continue
            else:
                print(f" Processing {max_pages*POST_AMOUNT} out of {COUNT} resul\
ts.")
            break
        return {'post': data}

    def get_post(self, add_tags, max_pages=10, id=''):
        return self.get_data(add_tags, user_tagged, max_pages, "&id=" + id)


class Konachan(Booru):

    def __init__(self):
        super().__init__('konachan', f'https://konachan.com/post.json?limit={POS\
T_AMOUNT}')

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''):
        global COUNT
        loop_msg = True # avoid showing same msg twice
        for loop in range(2): # run loop at most twice
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&page={random.randint(0, max_page\
s-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)
            data = res.json()
            COUNT = len(data)
            if COUNT == 0:
                max_pages = 2
                # Konachan does not have a way to know the amount of results ava\
ilable in the search, so we need to run the function again with a fixed amount o\
f pages
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                    # avoid showing same msg twice
                continue
            else:
                print(f"Found enough results")
            break
        return {'post': data}

    def get_post(self, add_tags, max_pages=10, id=''):
        raise Exception("Konachan does not support post IDs")


class Yandere(Booru):

    def __init__(self):
        super().__init__('yande.re', f'https://yande.re/post.json?limit={POST_AM\
OUNT}')

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''):
        global COUNT
        loop_msg = True # avoid showing same msg twice
        for loop in range(2): # run loop at most twice
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&page={random.randint(0, max_page\
s-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)
            data = res.json()
            COUNT = len(data)
            COUNT = len(data)
            if COUNT == 0:
                max_pages = 2
                # Yandere does not have a way to know the amount of results avai\
lable in the search, so we need to run the function again with a fixed amount of\
 pages
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                    # avoid showing same msg twice
                continue
            else:
                print(f"Found enough results")
            break
        return {'post': data}

    def get_post(self, add_tags, max_pages=10, id=''):
        raise Exception("Yande.re does not support post IDs")


class AIBooru(Booru):

    def __init__(self):
        super().__init__('AIBooru', f'https://aibooru.online/posts.json?limit={P\
OST_AMOUNT}')

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''):
        global COUNT
        loop_msg = True # avoid showing same msg twice
        for loop in range(2): # run loop at most twice
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&page={random.randint(0, max_page\
s-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)
            data = res.json()
            for post in data:
                post['tags'] = post['tag_string']
            COUNT = len(data)
            if COUNT == 0:
                max_pages = 2
                # AIBooru does not have a way to know the amount of results avai\
lable in the search, so we need to run the function again with a fixed amount of\
 pages
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                    # avoid showing same msg twice
                continue
            else:
                print(f"Found enough results")
            break
        return {'post': data}

    def get_post(self, add_tags, max_pages=10, id=''):
        raise Exception("AIBooru does not support post IDs")


class Danbooru(Booru):

    def __init__(self):
        super().__init__('danbooru', f'https://danbooru.donmai.us/posts.json?lim\
it={POST_AMOUNT}{DAN_API_AUTH}')

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''):
        if (DANBOORU_TIER == 'gold' or DANBOORU_TIER == 'platinum') and user_tag\
ged is False:
            max_pages = max_pages * 50
        else:
            max_pages = max_pages * 5
        global COUNT
        loop_msg = True # avoid showing same msg twice
        for loop in range(2): # run loop at most twice
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&page={random.randint(0, max_page\
s-1)}{id}{add_tags}"
            res = requests.get(self.booru_url, headers=self.headers)
            data = res.json()
            for post in data:
                post['tags'] = post['tag_string']
            COUNT = len(data)
            if COUNT == 0:
                max_pages = 2
                # Danbooru does not have a way to know the amount of results ava\
ilable in the search, so we need to run the function again with a fixed amount o\
f pages
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                    # avoid showing same msg twice
                continue
            else:
                print(f"Found enough results")
            break
        return {'post': data}

    def get_post(self, add_tags, max_pages=10, id=''):
        self.booru_url = f"https://danbooru.donmai.us/posts/{id}.json"
        res = requests.get(self.booru_url, headers=self.headers)
        data = res.json()
        data['tags'] = data['tag_string']
        data = {'post': [data]}
        return data


class e621(Booru):

    def __init__(self):
        super().__init__('e621', f'https://e621.net/posts.json?limit={POST_A\
MOUNT}') # Changed 'danbooru' to 'e621'

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''):
        global COUNT
        loop_msg = True # avoid showing same msg twice
        for loop in range(2): # run loop at most twice
            if id:
                add_tags = ''
            self.booru_url = f"{self.booru_url}&page={random.randint(0, max_page\
s-1)}{id}{add_tags}"
            res = requests.get(self.booru_url, headers=self.headers)
            data = res.json()['posts']
            COUNT = len(data)
            for post in data:
                temp_tags = []
                sublevels = ['general', 'artist', 'copyright', 'character', 'spe\
cies']
                for sublevel in sublevels:
                    temp_tags.extend(post['tags'][sublevel])
                post['tags'] = ' '.join(temp_tags)
                post['score'] = post['score']['total']
            if COUNT <= max_pages*POST_AMOUNT:
                max_pages = COUNT // POST_AMOUNT+1
                # If max_pages is bigger than available pages, loop the function\
 with updated max_pages based on the value of COUNT
                while loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                    # avoid showing same msg twice
                continue
            else:
                print(f" Processing {max_pages*POST_AMOUNT} out of {COUNT} resul\
ts.")
            break
        return {'post': data}

    def get_post(self, add_tags, max_pages=10, id=''):
        self.booru_url = f"https://e621.net/posts/{id}.json"
        res = requests.get(self.booru_url, headers=self.headers); data_res = res.json()
        data = data_res.get('post', {})
        if not data: return {'post': []}
        temp_tags = []; sublevels = ['general', 'artist', 'copyright', 'character', 'species']
        for sublevel in sublevels: temp_tags.extend(data.get('tags', {}).get(sublevel, []))
        data['tags'] = ' '.join(temp_tags)
        data['score'] = data.get('score', {}).get('total', 0)
        return {'post': [data]}


def generate_chaos(pos_tags, neg_tags, chaos_amount):
    """Generates chaos in the prompt by adding random tags from the prompt to th\
e positive and negative prompts

    Args:
        pos_tags (str): the positive prompt
        neg_tags (str): the negative prompt
        chaos_amount (float): the percentage of tags to put in the positive prom\
pt

    Returns:
        str: the positive prompt
        str: the negative prompt
    """
    # create a list with the tags in the prompt and in the negative prompt
    chaos_list = [tag for tag in pos_tags.split(',') + neg_tags.split(',') if ta\
g.strip() != '']
    # distinct the list
    chaos_list = list(set(chaos_list))
    random.shuffle(chaos_list)
    # put 50% of the tags in the prompt and the remaining 50% in the negative pr\
ompt
    len_list = round(len(chaos_list) * chaos_amount)
    pos_list = chaos_list[len_list:]
    pos_prompt = ','.join(pos_list)
    neg_list = chaos_list[:len_list]
    random.shuffle(neg_list)
    neg_prompt = ','.join(neg_list)
    return pos_prompt, neg_prompt


def resize_image(img, width, height, cropping=True):
    """Resize image to specified width and height

    Args:
        img (PIL.Image): the image
        width (int): the width in pixels
        height (int): the height in pixels
        cropping (bool): whether to crop the image or not

    Returns:
        PIL.Image: the resized image
    """
    if cropping:
        # resize the picture and center crop it
        # example: you have a 100x200 picture and width=300 and height=300
        # resize to 300x600 and crop to 300x300 from the center
        x, y = img.size
        if x < y:
            # scale to width keeping aspect ratio
            wpercent = (width / float(img.size[0]))
            hsize = int((float(img.size[1]) * float(wpercent)))
            img_new = img.resize((width, hsize))
            if img_new.size[1] < height:
                # scale to height keeping aspect ratio
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

        # crop center
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
    """Modifies the prompt based on the type_deepbooru selected

    Args:
        prompt (str): the prompt
        tagged_prompt (str): the prompt tagged by deepbooru
        type_deepbooru (str): the type of modification

    Returns:
        str: the modified prompt
    """
    if type_deepbooru == 'Add Before':
        return tagged_prompt + ',' + prompt
    elif type_deepbooru == 'Add After':
        return prompt + ',' + tagged_prompt
    elif type_deepbooru == 'Replace':
        return tagged_prompt
    return prompt

def remove_repeated_tags(prompt):
    """Removes the repeated tags keeping the same order

    Args:
        prompt (str): the prompt

    Returns:
        str: the prompt without repeated tags
    """
    prompt = prompt.split(',')
    new_prompt = []
    for tag in prompt:
        if tag not in new_prompt:
            new_prompt.append(tag)
    return ','.join(new_prompt)

def limit_prompt_tags(prompt, limit_tags, mode):
    """Limits the amount of tags in the prompt. It can be done by percentage or\
 by a fixed amount.

    Args:
        prompt (str): the prompt
        limit_tags (float): the percentage of tags to keep
        mode (str): 'Limit' or 'Max'

    Returns:
        str: the prompt with the limited amount of tags
    """
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
    result_url = ''
    result_img = 'https://pic.re/image'

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
        default_file = 'tags_forbidden.txt'
        default_file_path = os.path.join(user_forbidden_prompt_dir, default_file)
        if not files and not os.path.exists(default_file_path):
            with open(default_file_path, 'w') as f: f.write("# Add tags here, one per line\nartist_name_example\ncharacter_name_example\n")
            files.append(default_file)
        elif default_file not in files and not os.path.exists(default_file_path): # Check if default not in files list
             with open(default_file_path, 'w') as f: f.write("# Add tags here, one per line\nartist_name_example\ncharacter_name_example\n")
        if default_file not in files and os.path.exists(default_file_path): files.append(default_file) # Ensure default is added if it exists but wasn't listed
        return files if files else [default_file]

    def refresh_forbidden_files(self): return gr.update(choices=self.get_forbidden_files())

    def get_last_result(self):
        result_link = ''
        if self.result_img == 'https://pic.re/image':
            self.result_url = "No source found. Check out this random image."
        else:
            result_link = f"<a href='{self.result_url}'>Open source link in new\
 tab</a>"
        return self.result_url, result_link, self.result_img

    def ui(self, is_img2img):
        with InputAccordion(False, label="Ranbooru", elem_id=self.elem_id("ra_en\
able")) as enabled:
            with gr.Accordion("Image Result Source", open=False):
                result_id_button = gr.Button(value='Get last result', variant='p\
rimary', size='lg')
                with gr.Blocks():
                    result_id = gr.Textbox(label="Image source link", lines=1, m\
ax_lines=1, interactive=False)
                    result_id_link = gr.Markdown()
                result_image = gr.Image(label="Image", show_download_button=Fals\
e, interactive=False)
            with gr.Accordion("Ranbooru Parameters", open=False):
                booru = gr.Dropdown(
                    ["gelbooru", "rule34", "safebooru", "danbooru", "konachan", \
'yande.re', 'aibooru', 'xbooru', 'e621'], label="Booru", value="gelbooru")
                max_pages = gr.Slider(label="Max Pages", minimum=1, maximum=100,\
 value=100, step=1)
                gr.Markdown("""## Post""")
                post_id = gr.Textbox(lines=1, label="Post ID")
                gr.Markdown("""## Tags""")
            tags = gr.Textbox(lines=1, label="Tags to Search (Pre)", info="Use __wildcard__ to pick a random tag from user/wildcards/wildcard.txt")
                remove_tags = gr.Textbox(lines=1, label="Tags to Remove (Post)")
                mature_rating = gr.Radio(list(RATINGS['gelbooru']), label="Matur\
e Rating", value="All")
                remove_bad_tags = gr.Checkbox(label="Remove bad tags", value=Tru\
e)
                shuffle_tags = gr.Checkbox(label="Shuffle tags", value=True)
                change_dash = gr.Checkbox(label='Convert "_" to spaces', value=F\
alse)
                same_prompt = gr.Checkbox(label="Use same prompt for all images"\
, value=False)
                fringe_benefits = gr.Checkbox(label="Fringe Benefits", value=Tru\
e)
                limit_tags = gr.Slider(value=1.0, label="Limit tags", minimum=0.\
05, maximum=1.0, step=0.05)
                max_tags = gr.Slider(value=100, label="Max tags", minimum=1, max\
imum=100, step=1)
                change_background = gr.Radio(["Don't Change", "Add Background", \
"Remove Background", "Remove All"], label="Change Background", value="Don't Chan\
ge")
                change_color = gr.Radio(["Don't Change", "Colored", "Limited Pal\
ette", "Monochrome"], label="Change Color", value="Don't Change")
                sorting_order = gr.Radio(["Random", "High Score", "Low Score"], \
label="Sorting Order", value="Random")

                booru.change(get_available_ratings, booru, mature_rating)  # upd\
ate available ratings
                booru.change(show_fringe_benefits, booru, fringe_benefits)  # di\
splay fringe benefits checkbox if gelbooru is selected
                gr.Markdown("""\n---\n""")
                gr.Markdown("### Post-Fetch Prompt Tag Filtering")
                forbidden_prompt_tags_text = gr.Textbox(lines=2, label="Forbidden Prompt Tags (Manual Input)", info="Comma-separated. Tags to remove from prompt AFTER image selection.")
                use_forbidden_prompt_txt = gr.Checkbox(label="Use Forbidden Prompt Tags from file", value=False)
                choose_forbidden_prompt_txt = gr.Dropdown(self.get_forbidden_files(), label="Choose Forbidden Prompt Tags .txt file", value="tags_forbidden.txt")
                forbidden_refresh_btn = gr.Button("Refresh Forbidden Files"); gr.Markdown("""\n---\n""")
                with gr.Accordion("Img2Img", open=False):
                    use_img2img = gr.Checkbox(label="Use img2img", value=False)
                    use_ip = gr.Checkbox(label="Send to Controlnet", value=False\
)
                    denoising = gr.Slider(value=0.75, label="Denoising", minimum\
=0.05, maximum=1.0, step=0.05)
                    use_last_img = gr.Checkbox(label="Use last image as img2img"\
, value=False)
                    crop_center = gr.Checkbox(label="Crop Center", value=False)
                    use_deepbooru = gr.Checkbox(label="Use Deepbooru", value=Fal\
se)
                    type_deepbooru = gr.Radio(["Add Before", "Add After", "Repla\
ce"], label="Deepbooru Tags Position", value="Add Before")
                with gr.Accordion("File", open=False):
                    use_search_txt = gr.Checkbox(label="Use tags_search.txt", va\
lue=False)
                    choose_search_txt = gr.Dropdown(self.get_files(user_search_d\
ir), label="Choose tags_search.txt", value="")
                    search_refresh_btn = gr.Button("Refresh")
                    use_remove_txt = gr.Checkbox(label="Use tags_remove.txt", va\
lue=False)
                    choose_remove_txt = gr.Dropdown(self.get_files(user_remove_d\
ir), label="Choose tags_remove.txt", value="")
                    remove_refresh_btn = gr.Button("Refresh")
                with gr.Accordion("Extra", open=False):
                    with gr.Box():
                        mix_prompt = gr.Checkbox(label="Mix prompts", value=Fals\
e)
                        mix_amount = gr.Slider(value=2, label="Mix amount", mini\
mum=2, maximum=10, step=1)
                    with gr.Box():
                        chaos_mode = gr.Radio(["None", "Chaos", "Less Chaos"], l\
abel="Chaos Mode", value="None")
                        chaos_amount = gr.Slider(value=0.5, label="Chaos Amount\
 %", minimum=0.1, maximum=1, step=0.05)
                    with gr.Box():
                        negative_mode = gr.Radio(["None", "Negative"], label="Ne\
gative Mode", value="None")
                        use_same_seed = gr.Checkbox(label="Use same seed for all\
 pictures", value=False)
                    with gr.Box():
                        use_cache = gr.Checkbox(label="Use cache", value=True)
        with InputAccordion(False, label="LoRAnado", elem_id=self.elem_id("lo_en\
able")) as lora_enabled:
            with gr.Box():
                lora_lock_prev = gr.Checkbox(label="Lock previous LoRAs", value=\
False)
                lora_folder = gr.Textbox(lines=1, label="LoRAs Subfolder")
                lora_amount = gr.Slider(value=1, label="LoRAs Amount", minimum=1\
, maximum=10, step=1)
            with gr.Box():
                lora_min = gr.Slider(value=-1.0, label="Min LoRAs Weight", minim\
um=-1.0, maximum=1, step=0.1)
                lora_max = gr.Slider(value=1.0, label="Max LoRAs Weight", minimu\
m=-1.0, maximum=1.0, step=0.1)
                lora_custom_weights = gr.Textbox(lines=1, label="LoRAs Custom We\
ights")

        search_refresh_btn.click(
            fn=self.refresh_ser,
            inputs=[],
            outputs=[choose_search_txt]
        )

        remove_refresh_btn.click(
            fn=self.refresh_rem,
            inputs=[],
            outputs=[choose_remove_txt]
        )

        forbidden_refresh_btn.click(fn=self.refresh_forbidden_files, inputs=[], outputs=[choose_forbidden_prompt_txt])

        result_id_button.click(
            fn=self.get_last_result,
            inputs=[],
            outputs=[result_id, result_id_link, result_image]
        )

        return [enabled, tags, booru, remove_bad_tags, max_pages, change_dash, s\
ame_prompt, fringe_benefits, remove_tags, use_img2img, denoising, use_last_img, \
change_background, change_color, shuffle_tags, post_id, mix_prompt, mix_amount, \
chaos_mode, negative_mode, chaos_amount, limit_tags, max_tags, sorting_order, ma\
ture_rating, lora_folder, lora_amount, lora_min, lora_max, lora_enabled, lora_cu\
stom_weights, lora_lock_prev, use_ip, use_search_txt, use_remove_txt, choose_sea\
rch_txt, choose_remove_txt, search_refresh_btn, remove_refresh_btn, forbidden_prompt_tags_text, use_forbidden_prompt_txt, choose_forbidden_prompt_txt, crop_center,\
 use_deepbooru, type_deepbooru, use_same_seed, use_cache]

    def check_orientation(self, img):
        """Check if image is portrait, landscape or square"""
        x, y = img.size
        if x / y > 1.2:
            return [768, 512]
        elif y / x > 1.2:
            return [512, 768]
        else:
            return [768, 768]

    def loranado(self, lora_enabled, lora_folder, lora_amount, lora_min, lora_ma\
x, lora_custom_weights, p, lora_lock_prev):
        lora_prompt = ''
        if lora_enabled:
            if lora_lock_prev:
                lora_prompt = self.previous_loras
            else:
                loras_path = os.path.join(shared.cmd_opts.lora_dir, lora_folder) if hasattr(shared, 'cmd_opts') and hasattr(shared.cmd_opts, 'lora_dir') else f'models/Lora/{lora_folder}'
                if not os.path.exists(loras_path): print(f"LoRA folder not found: {loras_path}"); return p
                loras = os.listdir(loras_path)
                # get only .safetensors files
                loras = [lora.replace('.safetensors', '') for lora in loras if lora.endswith('.safetensors')]
                if not loras: print(f"No LoRAs found in {loras_path}"); return p
                for l_idx in range(0, lora_amount): # Kilvoctu - renamed l to l_idx to avoid conflict with lora_custom_weights.split(',')
                    lora_weight = 0
                    custom_weights_list = lora_custom_weights.split(',') # Kilvoctu - Defined list
                    if lora_custom_weights != '' and l_idx < len(custom_weights_list): # Kilvoctu - Check index for custom weights
                        try: # Kilvoctu - Added try-except for safety
                            lora_weight = float(custom_weights_list[l_idx])
                        except ValueError:
                            lora_weight = round(random.uniform(lora_min, lora_max), 1) # Fallback to random
                    else: # If no custom weight for this LoRA, or no custom weights at all
                        lora_weight = round(random.uniform(lora_min, lora_max), 1)

                    while lora_weight == 0 and (lora_min != 0 or lora_max !=0) : lora_weight = round(random.uniform(lora_min, lora_max), 1) # Avoid infinite loop if min=max=0
                    lora_prompt += f'<lora:{random.choice(loras)}:{lora_weight}>'
                self.previous_loras = lora_prompt
        if lora_prompt:
            if isinstance(p.prompt, list):
                for num, pr in enumerate(p.prompt):
                    p.prompt[num] = f'{lora_prompt} {pr}'
            else:
                p.prompt = f'{lora_prompt} {p.prompt}'
        return p

    def before_process(self, p, enabled, tags, booru, remove_bad_tags, max_pages\
, change_dash, same_prompt, fringe_benefits, remove_tags, use_img2img, denoising\
, use_last_img, change_background, change_color, shuffle_tags, post_id, mix_prom\
pt, mix_amount, chaos_mode, negative_mode, chaos_amount, limit_tags, max_tags, s\
orting_order, mature_rating, lora_folder, lora_amount, lora_min, lora_max, lora_\
enabled, lora_custom_weights, lora_lock_prev, use_ip, use_search_txt, use_remove\
_txt, choose_search_txt, choose_remove_txt, search_refresh_btn, remove_refresh_b\
tn, forbidden_prompt_tags_text, use_forbidden_prompt_txt, choose_forbidden_prompt_txt, crop_center, use_deepbooru, type_deepbooru, use_same_seed, use_cache):
        # Manage Cache
        if use_cache and not requests_cache.patcher.is_installed():
            requests_cache.install_cache('ranbooru_cache', backend='sqlite', exp\
ire_after=3600)
        elif not use_cache and requests_cache.patcher.is_installed():
            requests_cache.uninstall_cache()
        if enabled:
            # Initialize APIs
            booru_apis = {
                'gelbooru': Gelbooru(fringe_benefits),
                'rule34': Rule34(),
                'safebooru': Safebooru(),
                'danbooru': Danbooru(),
                'konachan': Konachan(),
                'yande.re': Yandere(),
                'aibooru': AIBooru(),
                'xbooru': XBooru(),
                'e621': e621(),
            }
            self.original_prompt = p.prompt

            # Process wildcards on initial tags from UI
            tags = self.process_wildcards(tags) # 'tags' is from UI input

            # Check if compatible
            check_exception(booru, {'tags': tags, 'post_id': post_id})

            # Manage Bad Tags
            bad_tags = []
            if remove_bad_tags:
                bad_tags = ['mixed-language_text', 'watermark', 'text', 'english\
_text', 'speech_bubble', 'signature', 'artist_name', 'censored', 'bar_censor', '\
translation', 'twitter_username', "twitter_logo", 'patreon_username', 'commentar\
y_request', 'tagme', 'commentary', 'character_name', 'mosaic_censoring', 'instag\
ram_username', 'text_focus', 'english_commentary', 'comic', 'translation_request\
', 'fake_text', 'translated', 'paid_reward_available', 'thought_bubble', 'multip\
le_views', 'silent_comic', 'out-of-frame_censoring', 'symbol-only_commentary', '\
3koma', '2koma', 'character_watermark', 'spoken_question_mark', 'japanese_text',\
 'spanish_text', 'language_text', 'fanbox_username', 'commission', 'original', '\
ai_generated', 'stable_diffusion', 'tagme_(artist)', 'text_bubble', 'qr_code', '\
chinese_commentary', 'korean_text', 'partial_commentary', 'chinese_text', 'copyr\
ight_request', 'heart_censor', 'censored_nipples', 'page_number', 'scan', 'fake_\
magazine_cover', 'korean_commentary']

            if ',' in remove_tags:
                bad_tags.extend(remove_tags.split(','))
            else:
                bad_tags.append(remove_tags)

            if use_remove_txt:
                bad_tags.extend(open(os.path.join(user_remove_dir, choose_remove\
_txt), 'r').read().split(','))

            # Manage Backgrounds
            background_options = {
                'Add Background': ('detailed_background,' + random.choice(["outd\
oors", "indoors"]), COLORED_BG),
                'Remove Background': ('plain_background,simple_background,' + ra\
ndom.choice(COLORED_BG), ADD_BG),
                'Remove All': ('', COLORED_BG + ADD_BG)
            }

            if change_background in background_options:
                prompt_addition, tags_to_remove = background_options[change_back\
ground]
                bad_tags.extend(tags_to_remove)
                p.prompt = f'{p.prompt},{prompt_addition}' if p.prompt else prom\
pt_addition

            # Manage Colors
            color_options = {
                'Colored': BW_BG,
                'Limited Palette': '(limited_palette:1.3)',
                'Monochrome': ','.join(BW_BG)
            }

            if change_color in color_options:
                color_option = color_options[change_color]
                if isinstance(color_option, list):
                    bad_tags.extend(color_option)
                else:
                    p.prompt = f'{p.prompt},{color_option}' if p.prompt else col\
or_option

            if use_search_txt:
                search_tags = open(os.path.join(user_search_dir, choose_search_t\
xt), 'r').read()
                search_tags_r = search_tags.replace(" ", "")
                split_tags = search_tags_r.splitlines()
                filtered_tags = [line for line in split_tags if line.strip()]
                rand_selected = random.randint(0, len(filtered_tags) - 1)
                selected_tags = filtered_tags[rand_selected]
                tags = f'{tags},{selected_tags}' if tags else selected_tags

            add_tags = '&tags=-animated'
            user_tagged = False
            if tags:
                user_tagged = True
                add_tags += f'+{tags.replace(",", "+")}'
            if mature_rating != 'All':
                # rating does not count towards danbooru's tag limit
                add_tags += f'+rating:{RATINGS[booru][mature_rating]}'

            # Getting Data
            random_post = {'preview_url': ''}
            prompts = []
            last_img = []
            preview_urls = []
            api_url = booru_apis.get(booru, Gelbooru(fringe_benefits))
            print(f'Using {booru}')

            # Manage Post ID
            if post_id:
                data = api_url.get_post(add_tags, max_pages, post_id)
            else:
                data = api_url.get_data(add_tags, user_tagged, max_pages)

            print(api_url.booru_url)
            # Replace null scores with 0s
            for post in data['post']:
                post['score'] = post.get('score', 0)
            # Sort based on sorting_order
            if sorting_order == 'High Score':
                data['post'] = sorted(data['post'], key=lambda k: k.get('score',\
 0), reverse=True)
            elif sorting_order == 'Low Score':
                data['post'] = sorted(data['post'], key=lambda k: k.get('score',\
 0))
            if post_id:
                print(f'Using post ID: {post_id}')
                random_numbers = [0 for _ in range(0, p.batch_size * p.n_iter)]
            else:
                random_numbers = self.random_number(sorting_order, p.batch_size\
 * p.n_iter)
            for random_number in random_numbers:
                if same_prompt:
                    random_post = data['post'][random_numbers[0]]
                else:
                    if mix_prompt:
                        temp_tags = []
                        max_tags = 0
                        for _ in range(0, mix_amount):
                            if not post_id:
                                random_mix_number = self.random_number(sorting_o\
rder, 1)[0]
                            temp_tags.extend(data['post'][random_mix_number]['ta\
gs'].split(' '))
                            max_tags = max(max_tags, len(data['post'][random_mix\
_number]['tags'].split(' ')))
                        # distinct temp_tags
                        temp_tags = list(set(temp_tags))
                        random_post = data['post'][random_number]
                        max_tags = min(max(len(temp_tags), 20), max_tags)
                        random_post['tags'] = ' '.join(random.sample(temp_tags,\
max_tags))
                    else:
                        try:
                            random_post = data['post'][random_number]
                        except IndexError:
                            raise Exception(
                                "No posts found with those tags. Try lowering th\
e pages or changing the tags.")
                clean_tags = random_post['tags'].replace('(', r'\(').replace(')'\
, r'\)')
                temp_tags = random.sample(clean_tags.split(' '), len(clean_tags.\
split(' '))) if shuffle_tags else clean_tags.split(' ')
                prompts.append(','.join(temp_tags))
                preview_urls.append(random_post.get('file_url', 'https://pic.re/\
image'))
                self.result_url = f"{BOORU_ENDPOINTS[booru]}{random_post['id']}"
                keys_to_check = ['sample_url', 'large_file_url', 'file_url', ('f\
ile', 'url')]
                for key in keys_to_check:
                    try:
                        if isinstance(key, tuple):
                            self.result_img = random_post['file']['url']
                            break
                        else:
                            value = random_post[key]
                            if value:
                                self.result_img = value
                                break
                    except KeyError:
                        self.result_img = 'https://pic.re/image'
                # Debug picture
                if DEBUG:
                    print(random_post)
            # Get Images
            if use_img2img or use_deepbooru:
                image_urls = [random_post['file_url']] if use_last_img else prev\
iew_urls

                for img in image_urls:
                    response = requests.get(img, headers=api_url.headers)
                    last_img.append(Image.open(BytesIO(response.content)))
            new_prompts = []
            # Cleaning Tags
            for prompt in prompts:
                prompt_tags = [tag for tag in html.unescape(prompt).split(',') i\
f tag.strip() not in bad_tags]
                for bad_tag in bad_tags:
                    if '*' in bad_tag:
                        prompt_tags = [tag for tag in prompt_tags if bad_tag.rep\
lace('*', '') not in tag]
                new_prompt = ','.join(prompt_tags)
                if change_dash:
                    new_prompt = new_prompt.replace("_", " ")
                new_prompts.append(new_prompt)
            prompts = new_prompts

            # --- BEGIN KILVOCTU MODIFIED FORBIDDEN PROMPT TAGS FILTERING (applies only to ranbooru_prompts) ---
            # This section was moved and adapted from the original script's before_process logic
            forbidden_tags_to_apply = set()
            if forbidden_prompt_tags_text: # from UI
                forbidden_tags_to_apply.update(tag.strip().lower() for tag in forbidden_prompt_tags_text.split(',') if tag.strip())
            if use_forbidden_prompt_txt and choose_forbidden_prompt_txt: # from file
                try:
                    forbidden_file_path = os.path.join(user_forbidden_prompt_dir, choose_forbidden_prompt_txt)
                    if os.path.exists(forbidden_file_path):
                        with open(forbidden_file_path, 'r', encoding='utf-8') as f:
                            forbidden_tags_to_apply.update(line.strip().lower() for line in f if line.strip() and not line.startswith('#'))
                except Exception as e: print(f"Error reading chosen forbidden tags file {choose_forbidden_prompt_txt}: {e}")

            if forbidden_tags_to_apply:
                filtered_ranbooru_prompts_final = []
                for tag_string in prompts: # prompts is now a list of strings
                    tags_list_current = [tag.strip() for tag in tag_string.split(',') if tag.strip()]
                    kept_tags = [tag for tag in tags_list_current if tag.lower() not in forbidden_tags_to_apply]
                    filtered_ranbooru_prompts_final.append(','.join(kept_tags))
                prompts = filtered_ranbooru_prompts_final
            # --- END KILVOCTU MODIFIED FORBIDDEN PROMPT TAGS FILTERING ---

            if len(prompts) == 1:
                print('Processing Single Prompt')
                p.prompt = f"{p.prompt},{prompts[-1]}" if p.prompt else prompts[\
-1]
                if chaos_mode in ['Chaos', 'Less Chaos']:
                    negative_prompt = '' if chaos_mode == 'Less Chaos' else p.ne\
gative_prompt
                    p.prompt, negative_prompt = generate_chaos(p.prompt, negativ\
e_prompt, chaos_amount)
                    p.negative_prompt = f"{p.negative_prompt},{negative_prompt}"\
 if p.negative_prompt else negative_prompt
            else:
                print('Processing Multiple Prompts')
                negative_prompts = []
                new_prompts = []
                if chaos_mode == 'Chaos':
                    for prompt in prompts:
                        tmp_prompt, negative_prompt = generate_chaos(prompt, p.n\
egative_prompt, chaos_amount)
                        new_prompts.append(tmp_prompt)
                        negative_prompts.append(negative_prompt)
                    prompts = new_prompts
                    p.negative_prompt = negative_prompts
                elif chaos_mode == 'Less Chaos':
                    for prompt in prompts:
                        tmp_prompt, negative_prompt = generate_chaos(prompt, '',\
 chaos_amount)
                        new_prompts.append(tmp_prompt)
                        negative_prompts.append(negative_prompt)
                    prompts = new_prompts
                    p.negative_prompt = [p.negative_prompt + ',' + negative_prom\
pt for negative_prompt in negative_prompts]
                else:
                    p.negative_prompt = [p.negative_prompt for _ in range(0, p.b\
atch_size * p.n_iter)]
                p.prompt = prompts if not p.prompt else [f"{p.prompt},{prompt}" \
for prompt in prompts]
                if use_img2img:
                    if len(last_img) < p.batch_size * p.n_iter:
                        last_img = [last_img[0] for _ in range(0, p.batch_size *\
 p.n_iter)]
            if negative_mode == 'Negative':
                # remove tags from p.prompt using tags from the original prompt
                orig_list = self.original_prompt.split(',')
                if isinstance(p.prompt, list):
                    new_positive_prompts = []
                    new_negative_prompts = []
                    for pr, npp in zip(p.prompt, p.negative_prompt):
                        clean_prompt = pr.split(',')
                        clean_prompt = [tag for tag in clean_prompt if tag not i\
n orig_list]
                        clean_prompt = ','.join(clean_prompt)
                        new_positive_prompts.append(self.original_prompt)
                        new_negative_prompts.append(f'{npp},{clean_prompt}')
                    p.prompt = new_positive_prompts
                    p.negative_prompt = new_negative_prompts
                else:
                    clean_prompt = p.prompt.split(',')
                    clean_prompt = [tag for tag in clean_prompt if tag not in or\
ig_list]
                    clean_prompt = ','.join(clean_prompt)
                    p.negative_prompt = f'{p.negative_prompt},{clean_prompt}'
                    p.prompt = self.original_prompt
            if negative_mode == 'Negative' or chaos_mode in ['Chaos', 'Less Chao\
s']:
                # NEGATIVE PROMPT FIX
                neg_prompt_tokens = []
                for pr in p.negative_prompt:
                    neg_prompt_tokens.append(model_hijack.get_prompt_lengths(pr)\
[1])
                if len(set(neg_prompt_tokens)) != 1:
                    print('Padding negative prompts')
                    max_tokens = max(neg_prompt_tokens)
                    for num, neg in enumerate(neg_prompt_tokens):
                        while neg < max_tokens:
                            p.negative_prompt[num] += random.choice(p.negative_p\
rompt[num].split(','))
                            # p.negative_prompt[num] += '_'
                            neg = model_hijack.get_prompt_lengths(p.negative_pro\
mpt[num])[1]

            if limit_tags < 1:
                if isinstance(p.prompt, list):
                    p.prompt = [limit_prompt_tags(pr, limit_tags, 'Limit') for p\
r in p.prompt]
                else:
                    p.prompt = limit_prompt_tags(p.prompt, limit_tags, 'Limit')

            if max_tags > 0:
                if isinstance(p.prompt, list):
                    p.prompt = [limit_prompt_tags(pr, max_tags, 'Max') for pr in\
 p.prompt]
                else:
                    p.prompt = limit_prompt_tags(p.prompt, max_tags, 'Max')

            if use_same_seed:
                p.seed = random.randint(0, 2 ** 32 - 1) if p.seed == -1 else p.s\
eed
                p.seed = [p.seed] * p.batch_size

            # LORANADO
            p = self.loranado(lora_enabled, lora_folder, lora_amount, lora_min, \
lora_max, lora_custom_weights, p, lora_lock_prev)
            if use_deepbooru and not use_img2img:
                self.last_img = last_img
                tagged_prompts = self.use_autotagger('deepbooru')

                if isinstance(p.prompt, list):
                    p.prompt = [modify_prompt(pr, tagged_prompts[num], type_deep\
booru) for num, pr in enumerate(p.prompt)]
                    p.prompt = [remove_repeated_tags(pr) for pr in p.prompt]
                else:
                    p.prompt = modify_prompt(p.prompt, tagged_prompts, type_deep\
booru)
                    p.prompt = remove_repeated_tags(p.prompt[0])

            if use_img2img:
                if not use_ip:
                    self.real_steps = p.steps
                    p.steps = 1
                    self.last_img = last_img
                if use_ip:
                    controlNetModule = importlib.import_module('extensions.sd-we\
bui-controlnet.scripts.external_code', 'external_code')
                    controlNetList = controlNetModule.get_all_units_in_processin\
g(p)
                    copied_network = controlNetList[0].__dict__.copy()
                    copied_network['enabled'] = True
                    copied_network['weight'] = denoising
                    array_img = np.array(last_img[0])
                    copied_network['image']['image'] = array_img
                    copied_networks = [copied_network] + controlNetList[1:]
                    controlNetModule.update_cn_script_in_processing(p, copied_ne\
tworks)

        elif lora_enabled:
            p = self.loranado(lora_enabled, lora_folder, lora_amount, lora_min, \
lora_max, lora_custom_weights, p, lora_lock_prev)

    def postprocess(self, p, processed, enabled, tags, booru, remove_bad_tags, m\
ax_pages, change_dash, same_prompt, fringe_benefits, remove_tags, use_img2img, d\
enoising, use_last_img, change_background, change_color, shuffle_tags, post_id, \
mix_prompt, mix_amount, chaos_mode, negative_mode, chaos_amount, limit_tags, max\
_tags, sorting_order, mature_rating, lora_folder, lora_amount, lora_min, lora_ma\
x, lora_enabled, lora_custom_weights, lora_lock_prev, use_ip, use_search_txt, us\
e_remove_txt, choose_search_txt, choose_remove_txt, search_refresh_btn, remove_r\
efresh_btn, forbidden_prompt_tags_text, use_forbidden_prompt_txt, choose_forbidden_prompt_txt, crop_center, use_deepbooru, type_deepbooru, use_same_seed, use_cache\
):
        if use_img2img and not use_ip and enabled and hasattr(self, 'last_img') and self.last_img: # Kilvoctu - Check self.last_img
            print('Using pictures for img2img in postprocess (batch aware)') # Kilvoctu - Updated print

            # Determine target width/height for img2img
            # If cropping, use p.width/p.height directly.
            # If not cropping, use orientation of the *first* image for the whole batch, or ensure images are already correctly sized.
            # For simplicity here, we'll assume if not cropping, images are prepared to a consistent size or first image's orientation is desired for all.
            p_width_img2img = p.width
            p_height_img2img = p.height

            processed_batch_images = []
            if crop_center:
                width, height = p.width, p.height
                self.last_img = [resize_image(img, width, height, cropping=True)\
 for img in self.last_img]
            else:
                width, height = self.check_orientation(self.last_img[0])
            final_prompts = p.prompt
            if use_deepbooru:
                tagged_prompts = self.use_autotagger('deepbooru')
                if isinstance(p.prompt, list):
                    final_prompts = [modify_prompt(pr, tagged_prompts[num], type\
_deepbooru) for num, pr in enumerate(p.prompt)]
                    final_prompts = [remove_repeated_tags(pr) for pr in final_pr\
ompts]
                else:
                    final_prompts = modify_prompt(p.prompt, tagged_prompts, type\
_deepbooru)
                    final_prompts = remove_repeated_tags(final_prompts)
            p = StableDiffusionProcessingImg2Img(
                sd_model=shared.sd_model,
                outpath_samples=shared.opts.outdir_samples or shared.opts.outdir\
_img2img_samples,
                outpath_grids=shared.opts.outdir_grids or shared.opts.outdir_img\
2img_grids,
                prompt=final_prompts,
                negative_prompt=p.negative_prompt,
                seed=p.seed,
                sampler_name=p.sampler_name,
                scheduler=p.scheduler,
                batch_size=p.batch_size,
                n_iter=p.n_iter,
                steps=self.real_steps,
                cfg_scale=p.cfg_scale,
                width=width,
                height=height,
                init_images=self.last_img,
                denoising_strength=denoising,
            )
            proc = process_images(p)
            processed.images = proc.images
            processed.infotexts = proc.infotexts
            if use_last_img:
                processed.images.append(self.last_img[0])
            else:
                for num, img in enumerate(self.last_img):
                    processed.images.append(img)
                    processed.infotexts.append(proc.infotexts[num + 1])

    def random_number(self, sorting_order, size):
        """Generates random numbers based on the sorting_order

        Args:
            sorting_order (str): the sorting order. It can be 'Random', 'High Sc\
ore' or 'Low Score'
            size (int): the amount of random numbers to generate

        Returns:
            list: the random numbers
        """
        global COUNT
        if COUNT > POST_AMOUNT: # Modified to use COUNT instead of POST_AMOUNT
            COUNT = POST_AMOUNT # If there are more than 100 images, use POST_AM\
OUNT
        weights = np.arange(COUNT, 0, -1)
        weights = weights / weights.sum()
        if sorting_order in ('High Score', 'Low Score'):
            random_numbers = np.random.choice(np.arange(COUNT), size=size, p=wei\
ghts, replace=False)
        else:
            random_numbers = random.sample(range(COUNT), size)
        return random_numbers

    def use_autotagger(self, model):
        """Use the autotagger to tag the images

        Args:
            model (str): the model to use. Right now only 'deepbooru' is support\
ed

        Returns:
            list: the tagged prompts
        """
        if model == 'deepbooru':
            if isinstance(self.original_prompt, str):
                orig_prompt = [self.original_prompt]
            else:
                orig_prompt = self.original_prompt
            deepbooru.model.start()
            for img, prompt in zip(self.last_img, orig_prompt):
                final_prompts = [prompt + ',' + deepbooru.model.tag_multi(img) f\
or img in self.last_img]
            deepbooru.model.stop()
            return final_prompts
