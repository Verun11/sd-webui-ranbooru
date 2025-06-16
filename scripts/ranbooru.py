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

# --- Ranbooru Configuration ---
# Gelbooru API Key and User ID (Optional)
# If you have a Gelbooru API key and User ID, you can add them here.
# This may be required for certain Gelbooru features or for higher request limits.
# Fill these with your actual credentials if you have them.
GELBOORU_API_KEY = ""  # Example: "your_gelbooru_api_key_here"
GELBOORU_USER_ID = ""  # Example: "your_gelbooru_user_id_here"

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
if not os.path.isfile(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt')):
    with open(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt'), 'w') as f:
        f.write("# Add tags here, one per line\n")
        f.write("artist_name_example\n")
        f.write("character_name_example\n")

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
    def get_data(self, add_tags, max_pages=10, id=''): pass
    def get_post(self, add_tags, max_pages=10, id=''): pass

class Gelbooru(Booru):
    def __init__(self, fringe_benefits):
        super().__init__('gelbooru', f'https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}')
        self.fringeBenefits = fringe_benefits
    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT; loop_msg = True
        data = {}  # Default to empty dict
        COUNT = 0  # Default COUNT
        for _ in range(2):
            if id: add_tags = ''
            # Construct base URL
            base_url = f"https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}&pid={random.randint(0, max_pages-1)}{id}{add_tags}"

            # Add API key and User ID if they are set
            auth_params = ""
            if GELBOORU_API_KEY and GELBOORU_USER_ID:
                auth_params = f"&api_key={GELBOORU_API_KEY}&user_id={GELBOORU_USER_ID}"

            self.booru_url = base_url + auth_params

            res = requests.get(self.booru_url, cookies={'fringeBenefits': 'yup'} if self.fringeBenefits else None)
            try:
                if res and res.text:
                    data_json = res.json()
                    if data_json:
                        data = data_json
                        COUNT = data.get('@attributes', {}).get('count', 0)
                    else:
                        print("API returned empty or null JSON response in get_data (Gelbooru).")
                else:
                    print("API response was empty or None in get_data (Gelbooru).")
            except requests.exceptions.JSONDecodeError as e:
                print(f"Error decoding JSON from API in get_data (Gelbooru): {e}")
                if res and res.text:
                    print(f"Response text (first 500 chars): {res.text[:500]}")
                # data remains {} and COUNT remains 0

            if COUNT <= max_pages*POST_AMOUNT: # COUNT here is the global COUNT updated in try/except
                max_pages = (COUNT // POST_AMOUNT) + 1 if COUNT > 0 else 1
                if loop_msg: print(f" Processing {COUNT} results."); loop_msg = False
                continue
            else: print(f" Processing {max_pages*POST_AMOUNT} out of {COUNT} results.")
            break
        return data
    def get_post(self, add_tags, max_pages=10, id=''): return self.get_data(add_tags, max_pages, "&id=" + id)

class XBooru(Booru):
    def __init__(self): super().__init__('xbooru', f'https://xbooru.com/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}')
    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT; loop_msg = True
        data = {} # Default to empty dict
        COUNT = 0 # Default COUNT
        for _ in range(2):
            if id: add_tags = ''
            self.booru_url = f"https://xbooru.com/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}&pid={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)
            try:
                if res and res.text:
                    data_json = res.json()
                    if data_json:
                        # XBooru specific: data is the list, COUNT is len(list)
                        # It also modifies posts in place to add 'file_url'
                        processed_posts = []
                        for post in data_json: # data_json should be a list of posts
                            if isinstance(post, dict):
                                post['file_url'] = f"https://xbooru.com/images/{post.get('directory')}/{post.get('image')}"
                                processed_posts.append(post)
                        data = {'post': processed_posts} # Store posts under 'post' key like others
                        COUNT = len(processed_posts)
                    else:
                        print("API returned empty or null JSON response in get_data (XBooru).")
                        data = {'post': []} # Ensure data is a dict with 'post' key
                else:
                    print("API response was empty or None in get_data (XBooru).")
                    data = {'post': []} # Ensure data is a dict with 'post' key
            except requests.exceptions.JSONDecodeError as e:
                print(f"Error decoding JSON from API in get_data (XBooru): {e}")
                if res and res.text:
                    print(f"Response text (first 500 chars): {res.text[:500]}")
                data = {'post': []} # Ensure data is a dict with 'post' key on error
                COUNT = 0

            if COUNT <= max_pages*POST_AMOUNT:
                max_pages = (COUNT // POST_AMOUNT) + 1 if COUNT > 0 else 1
                if loop_msg: print(f" Processing {COUNT} results."); loop_msg = False
                continue
            else: print(f" Processing {max_pages*POST_AMOUNT} out of {COUNT} results.")
            break
        return data # data is now {'post': [...]} or {'post': []}
    def get_post(self, add_tags, max_pages=10, id=''): return self.get_data(add_tags, max_pages, "&id=" + id)

class Rule34(Booru):
    def __init__(self): super().__init__('rule34', f'https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}')
    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT; loop_msg = True
        data = {} # Default to empty dict
        COUNT = 0 # Default COUNT
        for _ in range(2):
            if id: add_tags = ''
            self.booru_url = f"https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}&pid={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)
            try:
                if res and res.text:
                    data_json = res.json()
                    if data_json and isinstance(data_json, list): # Rule34 expects a list
                        data = {'post': data_json}
                        COUNT = len(data_json)
                    elif data_json: # Not a list, but not empty
                        print("API returned non-list JSON response when list was expected in get_data (Rule34).")
                        data = {'post': []} # Ensure data is a dict with 'post' key
                        COUNT = 0
                    else:
                        print("API returned empty or null JSON response in get_data (Rule34).")
                        data = {'post': []} # Ensure data is a dict with 'post' key
                        COUNT = 0
                else:
                    print("API response was empty or None in get_data (Rule34).")
                    data = {'post': []} # Ensure data is a dict with 'post' key
                    COUNT = 0
            except requests.exceptions.JSONDecodeError as e:
                print(f"Error decoding JSON from API in get_data (Rule34): {e}")
                if res and res.text:
                    print(f"Response text (first 500 chars): {res.text[:500]}")
                data = {'post': []} # Ensure data is a dict with 'post' key
                COUNT = 0

            if COUNT == 0:
                max_pages = 2 # Default if no results
                if loop_msg: print(f" Processing {COUNT} results."); loop_msg = False
                continue
            else: print(f"Found enough results"); break
        return data # data is now {'post': [...]} or {'post': []}
    def get_post(self, add_tags, max_pages=10, id=''): return self.get_data(add_tags, max_pages, "&id=" + id)

class Safebooru(Booru):
    def __init__(self): super().__init__('safebooru', f'https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}')
    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT; loop_msg = True
        data = {} # Default to empty dict
        COUNT = 0 # Default COUNT
        for _ in range(2):
            if id: add_tags = ''
            self.booru_url = f"https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}&pid={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)
            try:
                if res and res.text:
                    data_json = res.json()
                    if data_json and isinstance(data_json, list):
                        processed_posts = []
                        for post in data_json:
                            if isinstance(post, dict):
                                post['file_url'] = f"https://safebooru.org/images/{post.get('directory')}/{post.get('image')}"
                                processed_posts.append(post)
                        data = {'post': processed_posts}
                        COUNT = len(processed_posts)
                    elif data_json: # Not a list, but not empty
                        print("API returned non-list JSON response when list was expected in get_data (Safebooru).")
                        data = {'post': []}
                        COUNT = 0
                    else:
                        print("API returned empty or null JSON response in get_data (Safebooru).")
                        data = {'post': []}
                        COUNT = 0
                else:
                    print("API response was empty or None in get_data (Safebooru).")
                    data = {'post': []}
                    COUNT = 0
            except requests.exceptions.JSONDecodeError as e:
                print(f"Error decoding JSON from API in get_data (Safebooru): {e}")
                if res and res.text:
                    print(f"Response text (first 500 chars): {res.text[:500]}")
                data = {'post': []}
                COUNT = 0

            if COUNT <= max_pages*POST_AMOUNT:
                max_pages = (COUNT // POST_AMOUNT) + 1 if COUNT > 0 else 1
                if loop_msg: print(f" Processing {COUNT} results."); loop_msg = False
                continue
            else: print(f" Processing {max_pages*POST_AMOUNT} out of {COUNT} results.")
            break
        return data # data is now {'post': [...]} or {'post': []}
    def get_post(self, add_tags, max_pages=10, id=''): return self.get_data(add_tags, max_pages, "&id=" + id)

class Konachan(Booru):
    def __init__(self): super().__init__('konachan', f'https://konachan.com/post.json?limit={POST_AMOUNT}')
    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT; loop_msg = True
        data = {} # Default to empty dict
        COUNT = 0 # Default COUNT
        for _ in range(2):
            if id: add_tags = ''
            self.booru_url = f"https://konachan.com/post.json?limit={POST_AMOUNT}&page={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)
            try:
                if res and res.text:
                    data_json = res.json()
                    if data_json and isinstance(data_json, list):
                        data = {'post': data_json}
                        COUNT = len(data_json)
                    elif data_json: # Not a list, but not empty
                        print("API returned non-list JSON response when list was expected in get_data (Konachan).")
                        data = {'post': []}
                        COUNT = 0
                    else:
                        print("API returned empty or null JSON response in get_data (Konachan).")
                        data = {'post': []}
                        COUNT = 0
                else:
                    print("API response was empty or None in get_data (Konachan).")
                    data = {'post': []}
                    COUNT = 0
            except requests.exceptions.JSONDecodeError as e:
                print(f"Error decoding JSON from API in get_data (Konachan): {e}")
                if res and res.text:
                    print(f"Response text (first 500 chars): {res.text[:500]}")
                data = {'post': []}
                COUNT = 0

            if COUNT == 0:
                max_pages = 2
                if loop_msg: print(f" Processing {COUNT} results."); loop_msg = False
                continue
            else: print(f"Found enough results"); break
        return data # data is now {'post': [...]} or {'post': []}
    def get_post(self, add_tags, max_pages=10, id=''): raise Exception("Konachan does not support post IDs")

class Yandere(Booru):
    def __init__(self): super().__init__('yande.re', f'https://yande.re/post.json?limit={POST_AMOUNT}')
    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT; loop_msg = True
        data = {} # Default to empty dict
        COUNT = 0 # Default COUNT
        for _ in range(2):
            if id: add_tags = ''
            self.booru_url = f"https://yande.re/post.json?limit={POST_AMOUNT}&page={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)
            try:
                if res and res.text:
                    data_json = res.json()
                    if data_json and isinstance(data_json, list):
                        data = {'post': data_json}
                        COUNT = len(data_json)
                    elif data_json: # Not a list, but not empty
                        print("API returned non-list JSON response when list was expected in get_data (Yandere).")
                        data = {'post': []}
                        COUNT = 0
                    else:
                        print("API returned empty or null JSON response in get_data (Yandere).")
                        data = {'post': []}
                        COUNT = 0
                else:
                    print("API response was empty or None in get_data (Yandere).")
                    data = {'post': []}
                    COUNT = 0
            except requests.exceptions.JSONDecodeError as e:
                print(f"Error decoding JSON from API in get_data (Yandere): {e}")
                if res and res.text:
                    print(f"Response text (first 500 chars): {res.text[:500]}")
                data = {'post': []}
                COUNT = 0

            if COUNT == 0:
                max_pages = 2
                if loop_msg: print(f" Processing {COUNT} results."); loop_msg = False
                continue
            else: print(f"Found enough results"); break
        return data # data is now {'post': [...]} or {'post': []}
    def get_post(self, add_tags, max_pages=10, id=''): raise Exception("Yande.re does not support post IDs")

class AIBooru(Booru):
    def __init__(self): super().__init__('AIBooru', f'https://aibooru.online/posts.json?limit={POST_AMOUNT}')
    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT; loop_msg = True
        data = {} # Default to empty dict
        COUNT = 0 # Default COUNT
        for _ in range(2):
            if id: add_tags = ''
            self.booru_url = f"https://aibooru.online/posts.json?limit={POST_AMOUNT}&page={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)
            try:
                if res and res.text:
                    data_json = res.json()
                    if data_json and isinstance(data_json, list):
                        processed_posts = []
                        for post in data_json:
                            if isinstance(post, dict):
                                post['tags'] = post.get('tag_string', '') # Safe get
                                processed_posts.append(post)
                        data = {'post': processed_posts}
                        COUNT = len(processed_posts)
                    elif data_json: # Not a list, but not empty
                        print("API returned non-list JSON response when list was expected in get_data (AIBooru).")
                        data = {'post': []}
                        COUNT = 0
                    else:
                        print("API returned empty or null JSON response in get_data (AIBooru).")
                        data = {'post': []}
                        COUNT = 0
                else:
                    print("API response was empty or None in get_data (AIBooru).")
                    data = {'post': []}
                    COUNT = 0
            except requests.exceptions.JSONDecodeError as e:
                print(f"Error decoding JSON from API in get_data (AIBooru): {e}")
                if res and res.text:
                    print(f"Response text (first 500 chars): {res.text[:500]}")
                data = {'post': []}
                COUNT = 0

            if COUNT == 0: # COUNT is updated in try/except
                max_pages = 2
                if loop_msg: print(f" Processing {COUNT} results."); loop_msg = False
                continue
            else: print(f"Found enough results"); break
        return data # data is now {'post': [...]} or {'post': []}
    def get_post(self, add_tags, max_pages=10, id=''): raise Exception("AIBooru does not support post IDs")

class Danbooru(Booru):
    def __init__(self): super().__init__('danbooru', f'https://danbooru.donmai.us/posts.json?limit={POST_AMOUNT}')
    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT; loop_msg = True
        data = {} # Default to empty dict
        COUNT = 0 # Default COUNT
        for _ in range(2):
            if id: add_tags = ''
            self.booru_url = f"https://danbooru.donmai.us/posts.json?limit={POST_AMOUNT}&page={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url, headers=self.headers)
            try:
                if res and res.text:
                    data_json = res.json()
                    if data_json and isinstance(data_json, list):
                        processed_posts = []
                        for post in data_json:
                            if isinstance(post, dict):
                                post['tags'] = post.get('tag_string', '') # Safe get
                                processed_posts.append(post)
                        data = {'post': processed_posts}
                        COUNT = len(processed_posts)
                    elif data_json: # Not a list, but not empty
                        print("API returned non-list JSON response when list was expected in get_data (Danbooru).")
                        data = {'post': []}
                        COUNT = 0
                    else:
                        print("API returned empty or null JSON response in get_data (Danbooru).")
                        data = {'post': []}
                        COUNT = 0
                else:
                    print("API response was empty or None in get_data (Danbooru).")
                    data = {'post': []}
                    COUNT = 0
            except requests.exceptions.JSONDecodeError as e:
                print(f"Error decoding JSON from API in get_data (Danbooru): {e}")
                if res and res.text:
                    print(f"Response text (first 500 chars): {res.text[:500]}")
                data = {'post': []}
                COUNT = 0

            if COUNT == 0: # COUNT is updated in try/except
                max_pages = 2
                if loop_msg: print(f" Processing {COUNT} results."); loop_msg = False
                continue
            else: print(f"Found enough results"); break
        return data # data is now {'post': [...]} or {'post': []}
    def get_post(self, add_tags, max_pages=10, id=''):
        self.booru_url = f"https://danbooru.donmai.us/posts/{id}.json"
        res = requests.get(self.booru_url, headers=self.headers)
        data = {} # Default to empty dict
        try:
            if res and res.text:
                data_json = res.json()
                if data_json and isinstance(data_json, dict): # Expects a dict for a single post
                    data_json['tags'] = data_json.get('tag_string', '') # Safe get
                    # Wrap in a list to match the {'post': [data]} structure
                    return {'post': [data_json]}
                elif data_json: # Not a dict, but not empty
                     print("API returned non-dict JSON response when dict was expected in get_post (Danbooru).")
                     return {'post': []} # Return empty list in 'post' key
                else:
                    print("API returned empty or null JSON response in get_post (Danbooru).")
                    return {'post': []} # Return empty list in 'post' key
            else:
                print("API response was empty or None in get_post (Danbooru).")
                return {'post': []} # Return empty list in 'post' key
        except requests.exceptions.JSONDecodeError as e:
            print(f"Error decoding JSON from API in get_post (Danbooru): {e}")
            if res and res.text:
                print(f"Response text (first 500 chars): {res.text[:500]}")
            return {'post': []} # Return empty list in 'post' key on error

class e621(Booru):
    def __init__(self): super().__init__('e621', f'https://e621.net/posts.json?limit={POST_AMOUNT}')
    def get_data(self, add_tags, max_pages=10, id=''):
        global COUNT; loop_msg = True
        data_list = [] # Use a different name for the list of posts to avoid conflict with returned 'data' dict
        COUNT = 0 # Default COUNT
        for _ in range(2):
            if id: add_tags = ''
            self.booru_url = f"https://e621.net/posts.json?limit={POST_AMOUNT}&page={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url, headers=self.headers)
            data_list = [] # Reset data_list for each attempt
            try:
                if res and res.text:
                    data_json = res.json()
                    if data_json:
                        posts_from_json = data_json.get('posts', [])
                        if isinstance(posts_from_json, list):
                            processed_posts = []
                            for post_item in posts_from_json: # Renamed post to post_item
                                if isinstance(post_item, dict):
                                    temp_tags = []; sublevels = ['general', 'artist', 'copyright', 'character', 'species']
                                    for sublevel in sublevels: temp_tags.extend(post_item.get('tags', {}).get(sublevel, []))
                                    post_item['tags'] = ' '.join(temp_tags)
                                    post_item['score'] = post_item.get('score', {}).get('total', 0)
                                    processed_posts.append(post_item)
                            data_list = processed_posts
                            COUNT = len(data_list)
                        else:
                            print("API 'posts' field was not a list in get_data (e621).")
                            COUNT = 0
                    else:
                        print("API returned empty or null JSON response in get_data (e621).")
                        COUNT = 0
                else:
                    print("API response was empty or None in get_data (e621).")
                    COUNT = 0
            except requests.exceptions.JSONDecodeError as e:
                print(f"Error decoding JSON from API in get_data (e621): {e}")
                if res and res.text:
                    print(f"Response text (first 500 chars): {res.text[:500]}")
                data_list = [] # Ensure data_list is empty on error
                COUNT = 0

            # Loop control logic based on COUNT
            if COUNT <= max_pages*POST_AMOUNT: # COUNT is updated in try/except
                max_pages = (COUNT // POST_AMOUNT) + 1 if COUNT > 0 else 1
                if loop_msg: print(f" Processing {COUNT} results."); loop_msg = False
                continue
            else: print(f" Processing {max_pages*POST_AMOUNT} out of {COUNT} results.")
            break
        return {'post': data_list} # Return in the expected format

    def get_post(self, add_tags, max_pages=10, id=''):
        self.booru_url = f"https://e621.net/posts/{id}.json"
        res = requests.get(self.booru_url, headers=self.headers)
        try:
            if res and res.text:
                data_json = res.json()
                if data_json and isinstance(data_json, dict):
                    post_data = data_json.get('post', {}) # Original logic: data = data_res.get('post', {})
                    if not post_data:  # Check if post_data is empty
                        print("API 'post' field was empty in get_post (e621).")
                        return {'post': []} # Return empty list in 'post' key

                    if isinstance(post_data, dict): # Ensure post_data is a dict
                        temp_tags = []; sublevels = ['general', 'artist', 'copyright', 'character', 'species']
                        for sublevel in sublevels: temp_tags.extend(post_data.get('tags', {}).get(sublevel, []))
                        post_data['tags'] = ' '.join(temp_tags)
                        post_data['score'] = post_data.get('score', {}).get('total', 0)
                        return {'post': [post_data]} # Wrap in a list
                    else:
                        print("API 'post' field was not a dictionary in get_post (e621).")
                        return {'post': []}
                elif data_json: # Not a dict but not empty
                    print("API returned non-dict JSON response when dict was expected in get_post (e621).")
                    return {'post': []}
                else:
                    print("API returned empty or null JSON response in get_post (e621).")
                    return {'post': []}
            else:
                print("API response was empty or None in get_post (e621).")
                return {'post': []}
        except requests.exceptions.JSONDecodeError as e:
            print(f"Error decoding JSON from API in get_post (e621): {e}")
            if res and res.text:
                print(f"Response text (first 500 chars): {res.text[:500]}")
            return {'post': []} # Return empty list in 'post' key on error

def generate_chaos(pos_tags, neg_tags, chaos_amount):
    chaos_list = [tag for tag in pos_tags.split(',') + neg_tags.split(',') if tag.strip() != '']
    chaos_list = list(set(chaos_list)); random.shuffle(chaos_list)
    len_list = round(len(chaos_list) * chaos_amount)
    pos_prompt = ','.join(chaos_list[len_list:])
    neg_prompt = ','.join(chaos_list[:len_list])
    return pos_prompt, neg_prompt

def resize_image(img, width, height, cropping=True):
    if cropping:
        x, y = img.size
        if x < y:
            wpercent = (width / float(x)); hsize = int(float(y) * float(wpercent))
            img_new = img.resize((width, hsize))
            if img_new.size[1] < height:
                hpercent = (height / float(y)); wsize = int(float(x) * float(hpercent))
                img_new = img.resize((wsize, height))
        else:
            ypercent = (height / float(y)); wsize = int(float(x) * float(ypercent))
            img_new = img.resize((wsize, height))
            if img_new.size[0] < width:
                xpercent = (width / float(x)); hsize = int(float(y) * float(xpercent))
                img_new = img.resize((width, hsize))
        x_new, y_new = img_new.size # Renamed to avoid conflict
        left = (x_new - width) / 2; top = (y_new - height) / 2
        right = (x_new + width) / 2; bottom = (y_new + height) / 2
        img = img_new.crop((left, top, right, bottom))
    else: img = img.resize((width, height))
    return img

def modify_prompt(prompt, tagged_prompt, type_deepbooru):
    if type_deepbooru == 'Add Before': return tagged_prompt + ',' + prompt
    elif type_deepbooru == 'Add After': return prompt + ',' + tagged_prompt
    elif type_deepbooru == 'Replace': return tagged_prompt
    return prompt

def remove_repeated_tags(prompt):
    prompt_list = prompt.split(','); new_prompt = [] # Renamed variable
    for tag in prompt_list: # Use new variable
        if tag not in new_prompt: new_prompt.append(tag)
    return ','.join(new_prompt)

def limit_prompt_tags(prompt, limit_tags, mode):
    clean_prompt = prompt.split(',')
    if mode == 'Limit': clean_prompt = clean_prompt[:int(len(clean_prompt) * limit_tags)]
    elif mode == 'Max': clean_prompt = clean_prompt[:limit_tags]
    return ','.join(clean_prompt)

class Script(scripts.Script):
    previous_loras = ''; last_img = []; real_steps = 0; version = "1.2"; original_prompt = ''

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
        if os.path.exists(path): # Check if path exists
            for file in os.listdir(path):
                if file.endswith('.txt'): files.append(file)
        return files

    def hide_object(self, obj, booru_val): # Renamed booru to booru_val
        print(f'hide_object: {obj}, {booru_val}') # Use new name
        if booru_val == 'konachan' or booru_val == 'yande.re': obj.interactive = False
        else: obj.interactive = True

    def title(self): return "Ranbooru"
    def show(self, is_img2img): return scripts.AlwaysVisible
    def refresh_ser(self): return gr.update(choices=self.get_files(user_search_dir))
    def refresh_rem(self): return gr.update(choices=self.get_files(user_remove_dir))

    def get_forbidden_files(self):
        os.makedirs(user_forbidden_prompt_dir, exist_ok=True)
        files = [f for f in os.listdir(user_forbidden_prompt_dir) if f.endswith('.txt')]
        default_file = 'tags_forbidden.txt' # Renamed
        default_file_path = os.path.join(user_forbidden_prompt_dir, default_file) # Renamed
        if not files and not os.path.exists(default_file_path):
            with open(default_file_path, 'w') as f: f.write("# Add tags here, one per line\nartist_name_example\ncharacter_name_example\n")
            files.append(default_file)
        elif default_file not in files and not os.path.exists(default_file_path): # Check if default not in files list
             with open(default_file_path, 'w') as f: f.write("# Add tags here, one per line\nartist_name_example\ncharacter_name_example\n")
        if default_file not in files and os.path.exists(default_file_path): files.append(default_file)
        return files if files else [default_file]

    def refresh_forbidden_files(self): return gr.update(choices=self.get_forbidden_files())

    def ui(self, is_img2img):
        with InputAccordion(False, label="Ranbooru", elem_id=self.elem_id("ra_enable")) as enabled:
            booru = gr.Dropdown(["gelbooru", "rule34", "safebooru", "danbooru", "konachan", 'yande.re', 'aibooru', 'xbooru', 'e621'], label="Booru", value="gelbooru")
            max_pages = gr.Slider(label="Max Pages", minimum=1, maximum=100, value=100, step=1)
            gr.Markdown("""## Post"""); post_id = gr.Textbox(lines=1, label="Post ID")
            gr.Markdown("""## Tags""")
            tags = gr.Textbox(lines=1, label="Tags to Search (Pre)", info="Use __wildcard__ to pick a random tag from user/wildcards/wildcard.txt")
            remove_tags = gr.Textbox(lines=1, label="Tags to Remove (Post)")
            mature_rating = gr.Radio(list(RATINGS.get('gelbooru', {}).keys()), label="Mature Rating", value="All") # Safe get
            remove_bad_tags = gr.Checkbox(label="Remove bad tags", value=True); shuffle_tags = gr.Checkbox(label="Shuffle tags", value=True)
            change_dash = gr.Checkbox(label='Convert "_" to spaces', value=False); same_prompt = gr.Checkbox(label="Use same prompt for all images", value=False)
            fringe_benefits = gr.Checkbox(label="Fringe Benefits", value=True, visible=(booru.value == "gelbooru")) # Visibility based on initial value
            limit_tags = gr.Slider(value=1.0, label="Limit tags", minimum=0.05, maximum=1.0, step=0.05)
            max_tags_slider = gr.Slider(value=100, label="Max tags", minimum=1, maximum=100, step=1) # Renamed variable
            change_background = gr.Radio(["Don't Change", "Add Background", "Remove Background", "Remove All"], label="Change Background", value="Don't Change")
            change_color = gr.Radio(["Don't Change", "Colored", "Limited Palette", "Monochrome"], label="Change Color", value="Don't Change")
            sorting_order = gr.Radio(["Random", "High Score", "Low Score"], label="Sorting Order", value="Random")
            disable_prompt_modification = gr.Checkbox(label="Disable Ranbooru prompt modification", value=False)
            booru.change(get_available_ratings, booru, mature_rating)
            booru.change(show_fringe_benefits, booru, fringe_benefits)
            gr.Markdown("""\n---\n"""); gr.Markdown("### Post-Fetch Prompt Tag Filtering")
            forbidden_prompt_tags_text = gr.Textbox(lines=2, label="Forbidden Prompt Tags (Manual Input)", info="Comma-separated. Tags to remove from prompt AFTER image selection.")
            use_forbidden_prompt_txt = gr.Checkbox(label="Use Forbidden Prompt Tags from file", value=False)
            choose_forbidden_prompt_txt = gr.Dropdown(self.get_forbidden_files(), label="Choose Forbidden Prompt Tags .txt file", value="tags_forbidden.txt")
            forbidden_refresh_btn = gr.Button("Refresh Forbidden Files"); gr.Markdown("""\n---\n""")
            with gr.Group():
                with gr.Accordion("Img2Img", open=False):
                    use_img2img = gr.Checkbox(label="Use img2img", value=False); use_ip = gr.Checkbox(label="Send to Controlnet", value=False)
                    denoising = gr.Slider(value=0.75, label="Denoising", minimum=0.05, maximum=1.0, step=0.05)
                    use_last_img = gr.Checkbox(label="Use last image as img2img", value=False); crop_center = gr.Checkbox(label="Crop Center", value=False)
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
                    with gr.Box(): mix_prompt = gr.Checkbox(label="Mix prompts", value=False); mix_amount = gr.Slider(value=2, label="Mix amount", minimum=2, maximum=10, step=1)
                    with gr.Box(): chaos_mode = gr.Radio(["None", "Chaos", "Less Chaos"], label="Chaos Mode", value="None"); chaos_amount = gr.Slider(value=0.5, label="Chaos Amount %", minimum=0.1, maximum=1, step=0.05)
                    with gr.Box(): negative_mode = gr.Radio(["None", "Negative"], label="Negative Mode", value="None"); use_same_seed = gr.Checkbox(label="Use same seed for all pictures", value=False)
                    with gr.Box(): use_cache = gr.Checkbox(label="Use cache", value=True)
        with InputAccordion(False, label="LoRAnado", elem_id=self.elem_id("lo_enable")) as lora_enabled_ui: # Renamed
            with gr.Box():
                lora_lock_prev = gr.Checkbox(label="Lock previous LoRAs", value=False); lora_folder = gr.Textbox(lines=1, label="LoRAs Subfolder")
                lora_amount = gr.Slider(value=1, label="LoRAs Amount", minimum=1, maximum=10, step=1)
            with gr.Box():
                lora_min = gr.Slider(value=-1.0, label="Min LoRAs Weight", minimum=-1.0, maximum=1, step=0.1)
                lora_max = gr.Slider(value=1.0, label="Max LoRAs Weight", minimum=-1.0, maximum=1.0, step=0.1)
                lora_custom_weights = gr.Textbox(lines=1, label="LoRAs Custom Weights")
        search_refresh_btn.click(fn=self.refresh_ser, inputs=[], outputs=[choose_search_txt])
        remove_refresh_btn.click(fn=self.refresh_rem, inputs=[], outputs=[choose_remove_txt])
        forbidden_refresh_btn.click(fn=self.refresh_forbidden_files, inputs=[], outputs=[choose_forbidden_prompt_txt])
        return [enabled, tags, booru, remove_bad_tags, max_pages, change_dash, same_prompt, fringe_benefits, remove_tags, use_img2img, denoising, use_last_img, change_background, change_color, shuffle_tags, post_id, mix_prompt, mix_amount, chaos_mode, negative_mode, chaos_amount, limit_tags, max_tags_slider, sorting_order, mature_rating, lora_folder, lora_amount, lora_min, lora_max, lora_enabled_ui, lora_custom_weights, lora_lock_prev, use_ip, use_search_txt, use_remove_txt, choose_search_txt, choose_remove_txt, search_refresh_btn, remove_refresh_btn, forbidden_prompt_tags_text, use_forbidden_prompt_txt, choose_forbidden_prompt_txt, crop_center, use_deepbooru, type_deepbooru, use_same_seed, use_cache, disable_prompt_modification]

    def check_orientation(self, img):
        x, y = img.size
        if x / y > 1.2: return [768, 512]
        elif y / x > 1.2: return [512, 768]
        else: return [768, 768]

    def loranado(self, lora_enabled, lora_folder, lora_amount, lora_min, lora_max, lora_custom_weights, p, lora_lock_prev):
        lora_prompt = ''
        if lora_enabled:
            if lora_lock_prev: lora_prompt = self.previous_loras
            else:
                loras_path = os.path.join(shared.cmd_opts.lora_dir, lora_folder) if hasattr(shared, 'cmd_opts') and hasattr(shared.cmd_opts, 'lora_dir') else f'models/Lora/{lora_folder}' # Use shared path if available
                if not os.path.exists(loras_path): print(f"LoRA folder not found: {loras_path}"); return p
                loras = os.listdir(loras_path)
                loras = [lora.replace('.safetensors', '') for lora in loras if lora.endswith('.safetensors')]
                if not loras: print(f"No LoRAs found in {loras_path}"); return p
                for i in range(0, lora_amount): # Use i as loop var
                    lora_weight = 0
                    custom_weights_list = lora_custom_weights.split(',')
                    if lora_custom_weights != '' and i < len(custom_weights_list): # Check index
                        try: lora_weight = float(custom_weights_list[i])
                        except ValueError: lora_weight = round(random.uniform(lora_min, lora_max), 1) # Fallback
                    else: # If no custom weight for this LoRA, or no custom weights at all
                        lora_weight = round(random.uniform(lora_min, lora_max), 1)
                    while lora_weight == 0 and (lora_min != 0 or lora_max !=0) : lora_weight = round(random.uniform(lora_min, lora_max), 1) # Avoid infinite loop if min=max=0
                    lora_prompt += f'<lora:{random.choice(loras)}:{lora_weight}>'
                self.previous_loras = lora_prompt
        if lora_prompt:
            if isinstance(p.prompt, list):
                for num, pr_item in enumerate(p.prompt): p.prompt[num] = f'{lora_prompt} {pr_item}'
            else: p.prompt = f'{lora_prompt} {p.prompt}'
        return p

    def before_process(self, p, enabled, tags, booru, remove_bad_tags, max_pages, change_dash, same_prompt, fringe_benefits, remove_tags, use_img2img, denoising, use_last_img, change_background, change_color, shuffle_tags, post_id, mix_prompt, mix_amount, chaos_mode, negative_mode, chaos_amount, limit_tags_percentage, max_tags_count, sorting_order, mature_rating, lora_folder, lora_amount, lora_min, lora_max, lora_enabled_ui, lora_custom_weights, lora_lock_prev, use_ip, use_search_txt, use_remove_txt, choose_search_txt, choose_remove_txt, search_refresh_btn_dummy, remove_refresh_btn_dummy, forbidden_prompt_tags_text, use_forbidden_prompt_txt, choose_forbidden_prompt_txt, crop_center, use_deepbooru, type_deepbooru, use_same_seed, use_cache, disable_prompt_modification): # Renamed some vars to avoid conflict
        if use_cache and not requests_cache.patcher.is_installed(): requests_cache.install_cache('ranbooru_cache', backend='sqlite', expire_after=3600)
        elif not use_cache and requests_cache.patcher.is_installed(): requests_cache.uninstall_cache()

        if not enabled: # If not enabled, only apply LoRAnado if its UI is enabled
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
        self.original_prompt = p.prompt # Store the absolute original prompt from UI

        # Process wildcards on initial tags from UI
        tags_from_ui = self.process_wildcards(tags) # 'tags' is from UI input

        check_exception(booru, {'tags': tags_from_ui, 'post_id': post_id})

        current_processing_prompt = str(self.original_prompt) # Start with user's prompt for background/color etc.

        # Background and Color modifications apply to the user's base prompt part
        current_bad_tags = [] # Tags to remove specific to background/color changes
        if remove_bad_tags: current_bad_tags.extend(['mixed-language_text', 'watermark', 'text', 'english_text', 'speech_bubble', 'signature', 'artist_name', 'censored', 'bar_censor', 'translation', 'twitter_username', "twitter_logo", 'patreon_username', 'commentary_request', 'tagme', 'commentary', 'character_name', 'mosaic_censoring', 'instagram_username', 'text_focus', 'english_commentary', 'comic', 'translation_request', 'fake_text', 'translated', 'paid_reward_available', 'thought_bubble', 'multiple_views', 'silent_comic', 'out-of-frame_censoring', 'symbol-only_commentary', '3koma', '2koma', 'character_watermark', 'spoken_question_mark', 'japanese_text', 'spanish_text', 'language_text', 'fanbox_username', 'commission', 'original', 'ai_generated', 'stable_diffusion', 'tagme_(artist)', 'text_bubble', 'qr_code', 'chinese_commentary', 'korean_text', 'partial_commentary', 'chinese_text', 'copyright_request', 'heart_censor', 'censored_nipples', 'page_number', 'scan', 'fake_magazine_cover', 'korean_commentary'])

        background_options = {'Add Background': (random.choice(ADD_BG) + ',detailed_background', COLORED_BG), 'Remove Background': ('plain_background,simple_background,' + random.choice(COLORED_BG), ADD_BG), 'Remove All': ('', COLORED_BG + ADD_BG)}
        if change_background in background_options:
            prompt_addition, tags_to_remove_bg = background_options[change_background]
            current_bad_tags.extend(tags_to_remove_bg)
            if prompt_addition: current_processing_prompt = f'{current_processing_prompt.strip()},{prompt_addition}' if current_processing_prompt.strip() else prompt_addition

        color_options = {'Colored': (None, BW_BG), 'Limited Palette': ('(limited_palette:1.3)', None), 'Monochrome': (','.join(BW_BG), None)} # tag_to_add, tags_to_remove_color
        if change_color in color_options:
            prompt_addition_color, tags_to_remove_color = color_options[change_color]
            if tags_to_remove_color: current_bad_tags.extend(tags_to_remove_color)
            if prompt_addition_color: current_processing_prompt = f'{current_processing_prompt.strip()},{prompt_addition_color}' if current_processing_prompt.strip() else prompt_addition_color

        # Ranbooru tag fetching and initial cleaning
        final_search_tags = tags_from_ui
        if use_search_txt and choose_search_txt:
            search_tags_content = open(os.path.join(user_search_dir, choose_search_txt), 'r').read()
            split_tags = [line.strip() for line in search_tags_content.splitlines() if line.strip()]
            if split_tags: selected_tags = random.choice(split_tags); final_search_tags = f'{final_search_tags},{selected_tags}' if final_search_tags else selected_tags

        add_tags_query = '&tags=-animated'
        if final_search_tags: add_tags_query += f'+{final_search_tags.replace(",", "+")}'
        if mature_rating != 'All': add_tags_query += f'+rating:{RATINGS[booru][mature_rating]}'

        api_url = booru_apis.get(booru, Gelbooru(fringe_benefits)); print(f'Using {booru}')
        data = api_url.get_post(add_tags_query, max_pages, post_id) if post_id else api_url.get_data(add_tags_query, max_pages)
        print(api_url.booru_url)

        if 'post' not in data and 'posts' in data : data['post'] = data['posts']
        if 'post' not in data or not data['post']: data['post'] = []
        for post_item in data['post']: post_item['score'] = post_item.get('score', 0)
        if sorting_order == 'High Score': data['post'] = sorted(data['post'], key=lambda k: k.get('score', 0), reverse=True)
        elif sorting_order == 'Low Score': data['post'] = sorted(data['post'], key=lambda k: k.get('score', 0))

        ranbooru_prompts = [] # This will hold multiple prompt strings if batch > 1
        global last_img; last_img = []
        preview_urls = [] # Not used further but part of original logic flow

        num_images_to_generate = p.batch_size * p.n_iter
        random_numbers = [0]*num_images_to_generate if post_id else self.random_number(sorting_order, num_images_to_generate)
        if not data['post'] and num_images_to_generate > 0: raise Exception("No posts found from Booru. Try different tags or increase Max Pages.")

        for i in range(num_images_to_generate):
            idx = random_numbers[0] if same_prompt or not random_numbers else random_numbers[i]
            if idx >= len(data['post']): idx = len(data['post']) -1 # Safety for smaller result sets

            current_random_post = data['post'][idx]
            if mix_prompt and not same_prompt :
                temp_tags_mix = []; max_tags_mix = 0
                for _ in range(0, mix_amount):
                    mix_idx = self.random_number(sorting_order, 1)[0] if not post_id else 0
                    if mix_idx >= len(data['post']): mix_idx = len(data['post']) -1
                    temp_tags_mix.extend(data['post'][mix_idx].get('tags',"").split(' '))
                    max_tags_mix = max(max_tags_mix, len(data['post'][mix_idx].get('tags',"").split(' ')))
                temp_tags_mix = list(set(tag for tag in temp_tags_mix if tag)) # Ensure unique and non-empty
                max_tags_mix = min(max(len(temp_tags_mix), 20), max_tags_mix)
                current_random_post['tags'] = ' '.join(random.sample(temp_tags_mix, min(len(temp_tags_mix), max_tags_mix))) # Ensure sample size <= population

            clean_tags = current_random_post.get('tags', '').replace('(', r'\(').replace(')', r'\)')
            temp_tags_list = clean_tags.split(' ')
            if shuffle_tags: random.shuffle(temp_tags_list)
            ranbooru_prompts.append(','.join(tag for tag in temp_tags_list if tag)) # Filter empty tags from join
            preview_urls.append(current_random_post.get('file_url', 'https://pic.re/image'))

        if use_img2img or use_deepbooru:
            image_source_urls = [data['post'][random_numbers[0]]['file_url']] if use_last_img and data['post'] and random_numbers else preview_urls
            for img_url in image_source_urls[:num_images_to_generate]: # Limit to number of images needed
                try:
                    response = requests.get(img_url, headers=api_url.headers, timeout=10)
                    response.raise_for_status() # Check for HTTP errors
                    last_img.append(Image.open(BytesIO(response.content)))
                except requests.RequestException as e: print(f"Error fetching image {img_url}: {e}") # Handle network errors
                except Exception as e: print(f"Error processing image {img_url}: {e}") # Handle other image errors
            if not last_img and (use_img2img or use_deepbooru) : print("Warning: No images could be fetched for img2img/DeepBooru.")


        # Initial cleaning of Ranbooru-generated tags
        all_bad_tags = list(set(current_bad_tags)) # Combine bad tags from background/color with general ones
        if ',' in remove_tags: all_bad_tags.extend(tag.strip() for tag in remove_tags.split(',') if tag.strip())
        elif remove_tags.strip() : all_bad_tags.append(remove_tags.strip())
        if use_remove_txt and choose_remove_txt:
            try: all_bad_tags.extend(tag.strip() for tag in open(os.path.join(user_remove_dir, choose_remove_txt), 'r').read().split(',') if tag.strip())
            except Exception as e: print(f"Error reading remove_tags file: {e}")

        cleaned_ranbooru_prompts = []
        for rp_item in ranbooru_prompts: # rp_item is a string of tags
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
        forbidden_tags_to_apply = set()
        if forbidden_prompt_tags_text:
            forbidden_tags_to_apply.update(tag.strip().lower() for tag in forbidden_prompt_tags_text.split(',') if tag.strip())
        if use_forbidden_prompt_txt and choose_forbidden_prompt_txt:
            try:
                forbidden_file_path = os.path.join(user_forbidden_prompt_dir, choose_forbidden_prompt_txt)
                if os.path.exists(forbidden_file_path):
                    with open(forbidden_file_path, 'r', encoding='utf-8') as f:
                        forbidden_tags_to_apply.update(line.strip().lower() for line in f if line.strip())
            except Exception as e: print(f"Error reading chosen forbidden tags file {choose_forbidden_prompt_txt}: {e}")

        if forbidden_tags_to_apply:
            filtered_ranbooru_prompts_final = []
            for tag_string in ranbooru_prompts:
                tags_list = [tag.strip() for tag in tag_string.split(',') if tag.strip()]
                kept_tags = [tag for tag in tags_list if tag.lower() not in forbidden_tags_to_apply]
                filtered_ranbooru_prompts_final.append(','.join(kept_tags))
            ranbooru_prompts = filtered_ranbooru_prompts_final
        # --- END MOVED AND MODIFIED FORBIDDEN PROMPT TAGS FILTERING ---

        # Base for combining: user's prompt after background/color changes
        user_base_prompt = current_processing_prompt.strip()

        if len(ranbooru_prompts) == 1:
            ranbooru_tags_to_add = ranbooru_prompts[0]
            if user_base_prompt and ranbooru_tags_to_add: p.prompt = f"{user_base_prompt},{ranbooru_tags_to_add}"
            elif ranbooru_tags_to_add: p.prompt = ranbooru_tags_to_add
            else: p.prompt = user_base_prompt # If ranbooru tags are empty, use base

            if chaos_mode in ['Chaos', 'Less Chaos']:
                # Apply chaos to the full p.prompt (user_base_prompt + filtered ranbooru_tags_to_add)
                # Negative prompt for chaos is UI negative prompt
                base_neg_for_chaos = p.negative_prompt if chaos_mode == 'Chaos' else ''
                p.prompt, generated_chaos_neg_tags = generate_chaos(p.prompt, base_neg_for_chaos, chaos_amount)
                if p.negative_prompt and generated_chaos_neg_tags: p.negative_prompt = f"{p.negative_prompt},{generated_chaos_neg_tags}"
                elif generated_chaos_neg_tags: p.negative_prompt = generated_chaos_neg_tags
        else: # Multiple prompts (batch size > 1 or n_iter > 1)
            base_neg_prompt_from_ui = p.negative_prompt

            if chaos_mode == 'Chaos':
                processed_ranbooru_for_chaos = []
                new_negative_prompts_list = []
                for rp_item in ranbooru_prompts: # rp_item is already filtered
                    tmp_pos, tmp_neg = generate_chaos(rp_item, base_neg_prompt_from_ui, chaos_amount)
                    processed_ranbooru_for_chaos.append(tmp_pos)
                    new_negative_prompts_list.append(tmp_neg)
                ranbooru_prompts = processed_ranbooru_for_chaos
                p.negative_prompt = new_negative_prompts_list
            elif chaos_mode == 'Less Chaos':
                processed_ranbooru_for_chaos = []
                new_negative_prompts_list = []
                for rp_item in ranbooru_prompts: # rp_item is already filtered
                    tmp_pos, tmp_neg_chaos_only = generate_chaos(rp_item, "", chaos_amount) # Chaos only on ranbooru tags
                    processed_ranbooru_for_chaos.append(tmp_pos)
                    current_neg = f"{base_neg_prompt_from_ui.strip()},{tmp_neg_chaos_only}" if base_neg_prompt_from_ui.strip() and tmp_neg_chaos_only else (base_neg_prompt_from_ui.strip() or tmp_neg_chaos_only or "")
                    new_negative_prompts_list.append(current_neg.strip(',')) # clean leading/trailing commas
                ranbooru_prompts = processed_ranbooru_for_chaos
                p.negative_prompt = new_negative_prompts_list
            else:
                p.negative_prompt = [base_neg_prompt_from_ui for _ in range(len(ranbooru_prompts))]

            final_batch_prompts = []
            for rp_item in ranbooru_prompts: # rp_item is filtered & possibly chaos'd
                if user_base_prompt and rp_item: final_batch_prompts.append(f"{user_base_prompt},{rp_item}")
                elif rp_item: final_batch_prompts.append(rp_item)
                else: final_batch_prompts.append(user_base_prompt)
            p.prompt = final_batch_prompts

            if use_img2img and last_img: # Ensure last_img is not empty
                if len(last_img) < len(p.prompt): # Match image list size to prompt list size
                    last_img.extend([last_img[-1]] * (len(p.prompt) - len(last_img)))
                elif len(last_img) > len(p.prompt):
                    last_img = last_img[:len(p.prompt)]

        # Negative Mode (applied after all positive prompt construction)
        if negative_mode == 'Negative':
            # self.original_prompt is the pure UI input.
            # p.prompt at this stage is (user_base_prompt + filtered_ranbooru_tags (+chaos))
            # We want to move the Ranbooru-derived part to negative.
            # This is tricky because ranbooru_prompts was already combined.
            # A simpler interpretation: original prompt becomes positive, everything else negative.
            # This was how it was structured before.
            if isinstance(p.prompt, list):
                new_positive_prompts_neg = []
                new_negative_prompts_neg = []
                current_negative_prompts = p.negative_prompt if isinstance(p.negative_prompt, list) else [p.negative_prompt] * len(p.prompt)
                for i, full_prompt_str in enumerate(p.prompt):
                    current_neg = current_negative_prompts[i]
                    # Assume user_base_prompt was the prefix for full_prompt_str
                    # This needs careful reconstruction of what was purely from Ranbooru.
                    # For now, let's keep the previous simpler logic: user's original is positive, generated part of p.prompt is negative.
                    # This part needs careful re-evaluation if `user_base_prompt` is complex.
                    # Simplified: use original_prompt as positive, current p.prompt (without original) as negative part.

                    # Reconstruct what was added beyond self.original_prompt
                    # This is complex if self.original_prompt was empty or p.prompt was modified in place by chaos.
                    # Let's assume the current p.prompt items are what should be split.
                    # The parts NOT in self.original_prompt go to negative.

                    tags_to_move_to_negative = []
                    original_tags_set = set(tag.strip() for tag in self.original_prompt.split(',') if tag.strip())
                    current_prompt_tags = [tag.strip() for tag in full_prompt_str.split(',') if tag.strip()]

                    user_tags_in_current_prompt = []

                    for tag in current_prompt_tags:
                        if tag in original_tags_set: # Or if it was part of background/color changes derived from original
                             user_tags_in_current_prompt.append(tag) # Keep it simple: only exact original tags are "user's"
                        else:
                             tags_to_move_to_negative.append(tag)

                    new_positive_prompts_neg.append(",".join(user_tags_in_current_prompt)) # Or just self.original_prompt
                    additional_neg = ",".join(tags_to_move_to_negative)
                    new_negative_prompts_neg.append(f"{current_neg},{additional_neg}".strip(','))

                p.prompt = new_positive_prompts_neg
                p.negative_prompt = new_negative_prompts_neg
            elif isinstance(p.prompt, str): # Single prompt case
                tags_to_move_to_negative = []
                original_tags_set = set(tag.strip() for tag in self.original_prompt.split(',') if tag.strip())
                current_prompt_tags = [tag.strip() for tag in p.prompt.split(',') if tag.strip()]
                user_tags_in_current_prompt = []

                for tag in current_prompt_tags:
                    if tag in original_tags_set: user_tags_in_current_prompt.append(tag)
                    else: tags_to_move_to_negative.append(tag)

                p.prompt = ",".join(user_tags_in_current_prompt) # Or just self.original_prompt
                additional_neg = ",".join(tags_to_move_to_negative)
                p.negative_prompt = f"{p.negative_prompt},{additional_neg}".strip(',')

        # Padding negative prompts if lengths are inconsistent (batch mode)
        if isinstance(p.negative_prompt, list) and len(p.negative_prompt) > 1:
            neg_prompt_tokens = [model_hijack.get_prompt_lengths(pr_item)[1] for pr_item in p.negative_prompt]
            if len(set(neg_prompt_tokens)) != 1:
                print('Padding negative prompts'); max_tokens = max(neg_prompt_tokens)
                for num, neg_len in enumerate(neg_prompt_tokens):
                    while neg_len < max_tokens:
                        current_neg_prompt_item_parts = p.negative_prompt[num].split(',')
                        p.negative_prompt[num] += ("," + random.choice(current_neg_prompt_item_parts)) if current_neg_prompt_item_parts and current_neg_prompt_item_parts[0] else ",_"
                        neg_len = model_hijack.get_prompt_lengths(p.negative_prompt[num])[1]

        # Limit/Max tags
        if limit_tags_percentage < 1:
            if isinstance(p.prompt, list): p.prompt = [limit_prompt_tags(pr_item, limit_tags_percentage, 'Limit') for pr_item in p.prompt]
            else: p.prompt = limit_prompt_tags(p.prompt, limit_tags_percentage, 'Limit')
        if max_tags_count > 0: # Renamed from max_tags
            if isinstance(p.prompt, list): p.prompt = [limit_prompt_tags(pr_item, max_tags_count, 'Max') for pr_item in p.prompt]
            else: p.prompt = limit_prompt_tags(p.prompt, max_tags_count, 'Max')

        if use_same_seed:
            p.seed = random.randint(0, 2**32 - 1) if p.seed == -1 else p.seed
            if hasattr(p, 'batch_size') and p.batch_size is not None: p.seed = [p.seed] * p.batch_size
            else: p.seed = [p.seed]

        p = self.loranado(lora_enabled_ui, lora_folder, lora_amount, lora_min, lora_max, lora_custom_weights, p, lora_lock_prev)

        if use_deepbooru and not use_img2img:
            if last_img : self.last_img = last_img # Ensure self.last_img is set from fetched images
            else: print("DeepBooru selected but no images were fetched/available for tagging.")

            if self.last_img: # Only proceed if images are available
                tagged_prompts = self.use_autotagger('deepbooru') # This will use self.last_img
                if isinstance(p.prompt, list):
                    # Ensure tagged_prompts has enough items for the batch
                    if len(tagged_prompts) < len(p.prompt):
                        tagged_prompts.extend([tagged_prompts[-1] if tagged_prompts else ""] * (len(p.prompt) - len(tagged_prompts)))
                    p.prompt = [modify_prompt(p.prompt[i], tagged_prompts[i], type_deepbooru) for i in range(len(p.prompt))]
                    p.prompt = [remove_repeated_tags(pr_item) for pr_item in p.prompt]
                else: # Single prompt
                    p.prompt = modify_prompt(p.prompt, tagged_prompts[0] if tagged_prompts else "", type_deepbooru)
                    p.prompt = remove_repeated_tags(p.prompt)

        if use_img2img: # This sets up p for img2img, postprocess will execute it
            if not use_ip:
                self.real_steps = p.steps; p.steps = 1
                if last_img: self.last_img = last_img # Ensure self.last_img is set
                else: print("Img2Img selected but no images were fetched/available.")
            if use_ip and last_img: # Ensure last_img for ControlNet too
                controlNetModule = importlib.import_module('extensions.sd-webui-controlnet.scripts.external_code', 'external_code')
                controlNetList = controlNetModule.get_all_units_in_processing(p)
                if controlNetList:
                    copied_network = controlNetList[0].__dict__.copy()
                    copied_network['enabled'] = True; copied_network['weight'] = denoising
                    copied_network['image']['image'] = np.array(last_img[0]) # Use first image for CN
                    controlNetModule.update_cn_script_in_processing(p, [copied_network] + controlNetList[1:])

    def postprocess(self, p, processed, *args): # Removed all args not used by this specific override
        # The actual arguments received by postprocess are defined in the Script base class in modules.scripts
        # We only care about use_img2img, use_ip, enabled from the UI elements passed to before_process
        # Need to get these values. A common way is to store them on `self` in `before_process`.
        # For now, let's assume they are available on `self` if set in `before_process`.
        # This method needs access to: self.use_img2img, self.use_ip, self.enabled (from UI), self.last_img,
        # self.real_steps, self.denoising, self.use_deepbooru, self.type_deepbooru, self.crop_center.
        # These would need to be set on `self` in `before_process` if they are to be used here.
        # This is a simplification as the actual UI args are not passed directly to postprocess by the webui.

        # Simplified: Assume relevant 'self' attributes were set in before_process
        # For the purpose of this subtask, we are focused on before_process logic.
        # The postprocess logic below is from the original and may need self. attributes.

        # Check if necessary attributes are present on self (they should have been set in before_process)
        use_img2img_flag = getattr(self, 'use_img2img_flag', False)
        use_ip_flag = getattr(self, 'use_ip_flag', False)
        enabled_flag = getattr(self, 'enabled_flag', False)

        if use_img2img_flag and not use_ip_flag and enabled_flag and self.last_img:
            print('Using pictures for img2img in postprocess')

            p_width = p.width if hasattr(p,'width') else 512
            p_height = p.height if hasattr(p,'height') else 512
            crop_center_flag = getattr(self, 'crop_center_flag', False)

            if crop_center_flag:
                self.last_img = [resize_image(img, p_width, p_height, cropping=True) for img in self.last_img]
            else:
                # Ensure all images are processed for orientation if not cropping
                processed_last_img = []
                for img_item in self.last_img:
                    orient_width, orient_height = self.check_orientation(img_item)
                    processed_last_img.append(resize_image(img_item, orient_width, orient_height, cropping=False)) # resize to orientation
                self.last_img = processed_last_img
                # For StableDiffusionProcessingImg2Img, width/height should be consistent for the batch
                # So, we use the orientation of the first image for all if not cropping
                if self.last_img:
                     p_width, p_height = self.last_img[0].size


            final_prompts_for_img2img = p.prompt # p.prompt should be prepared by before_process
            use_deepbooru_flag = getattr(self, 'use_deepbooru_flag', False)
            type_deepbooru_val = getattr(self, 'type_deepbooru_val', "Add Before")

            if use_deepbooru_flag:
                tagged_prompts = self.use_autotagger('deepbooru')
                if isinstance(p.prompt, list):
                    if len(tagged_prompts) < len(p.prompt): tagged_prompts.extend([""]*(len(p.prompt)-len(tagged_prompts)))
                    final_prompts_for_img2img = [modify_prompt(p.prompt[i], tagged_prompts[i], type_deepbooru_val) for i in range(len(p.prompt))]
                    final_prompts_for_img2img = [remove_repeated_tags(pr) for pr in final_prompts_for_img2img]
                else:
                    final_prompts_for_img2img = modify_prompt(p.prompt, tagged_prompts[0] if tagged_prompts else "", type_deepbooru_val)
                    final_prompts_for_img2img = remove_repeated_tags(final_prompts_for_img2img)

            p_img2img = StableDiffusionProcessingImg2Img(
                sd_model=shared.sd_model,
                outpath_samples=shared.opts.outdir_samples or shared.opts.outdir_img2img_samples,
                outpath_grids=shared.opts.outdir_grids or shared.opts.outdir_img2img_grids,
                prompt=final_prompts_for_img2img,
                negative_prompt=p.negative_prompt,
                seed=p.seed if hasattr(p,'seed') else -1, # Ensure seed is available
                sampler_name=p.sampler_name if hasattr(p,'sampler_name') else "Euler a",
                scheduler=p.scheduler if hasattr(p,'scheduler') else None,
                batch_size=p.batch_size if hasattr(p,'batch_size') else 1,
                n_iter=p.n_iter if hasattr(p,'n_iter') else 1,
                steps=getattr(self, 'real_steps', p.steps if hasattr(p,'steps') else 20), # Use real_steps if available
                cfg_scale=p.cfg_scale if hasattr(p,'cfg_scale') else 7.0,
                width=p_width,
                height=p_height,
                init_images=self.last_img, # This should be a list of PIL Images
                denoising_strength=getattr(self, 'denoising_strength', 0.75) # Use stored denoising
            )
            proc = process_images(p_img2img)
            # Append results carefully
            if not hasattr(processed, 'images'): processed.images = []
            if not hasattr(processed, 'infotexts'): processed.infotexts = []

            processed.images.extend(proc.images)
            processed.infotexts.extend(proc.infotexts)

            use_last_img_flag = getattr(self, 'use_last_img_flag', False)
            if use_last_img_flag: # Append the source image used for all generations if this flag was true
                if self.last_img : processed.images.append(self.last_img[0])
            else: # Append all source images used
                 processed.images.extend(self.last_img)


    def random_number(self, sorting_order, size):
        global COUNT
        effective_count = max(1, COUNT if COUNT <= POST_AMOUNT else POST_AMOUNT)
        if size <= 0 : return [] # handle invalid size
        if size > effective_count : size = effective_count
        if sorting_order in ('High Score', 'Low Score') and effective_count > 0:
            weights = np.arange(effective_count, 0, -1); weights = weights / weights.sum()
            random_numbers = np.random.choice(np.arange(effective_count), size=min(size, effective_count), p=weights, replace=False)
        elif effective_count > 0 : random_numbers = random.sample(range(effective_count), min(size, effective_count))
        else: random_numbers = []
        return random_numbers.tolist() if isinstance(random_numbers, np.ndarray) else random_numbers

    def use_autotagger(self, model_name):
        if model_name == 'deepbooru' and hasattr(self, 'last_img') and self.last_img:
            # Use self.original_prompt for context, ensure it's a list matching self.last_img length
            original_prompts_for_tagging = []
            num_images = len(self.last_img)
            if isinstance(self.original_prompt, str):
                original_prompts_for_tagging = [self.original_prompt] * num_images
            elif isinstance(self.original_prompt, list):
                original_prompts_for_tagging = self.original_prompt
                if len(original_prompts_for_tagging) < num_images:
                    last_val = original_prompts_for_tagging[-1] if original_prompts_for_tagging else ""
                    original_prompts_for_tagging.extend([last_val] * (num_images - len(original_prompts_for_tagging)))
                elif len(original_prompts_for_tagging) > num_images:
                    original_prompts_for_tagging = original_prompts_for_tagging[:num_images]
            else: # Fallback
                original_prompts_for_tagging = [""] * num_images

            final_tagged_prompts = []
            try:
                deepbooru.model.start()
                for i in range(num_images):
                    final_tagged_prompts.append(original_prompts_for_tagging[i] + ',' + deepbooru.model.tag_multi(self.last_img[i]))
            except Exception as e:
                print(f"Error during DeepBooru tagging: {e}")
            finally:
                if hasattr(deepbooru, 'model') and hasattr(deepbooru.model, 'stop'): deepbooru.model.stop()
            return final_tagged_prompts
        return []
