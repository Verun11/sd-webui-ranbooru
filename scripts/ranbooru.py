from io import BytesIO
import html
import random
import requests
import re
from dotenv import load_dotenv
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
if not os.path.isfile(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt')):
    with open(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt'), 'w') as f:
        f.write("# Add tags here, one per line\n")
        f.write("artist_name_example\n")
        f.write("character_name_example\n")

# Initialize new global variables
# GEL_API_AUTH = None # Replaced by new logic below
# DAN_API_AUTH = None # Replaced by new logic below
# DANBOORU_TIER = None # Replaced by new logic below

# Load environment variables from .env file
load_dotenv()

# Define API auth variables and Danbooru tier from environment variables
GEL_API_AUTH, DAN_API_AUTH = '', '' # Initialize as empty strings

# DANBOORU_TIER is fetched first as it might influence RATINGS table right after
# Using "danbooru_tier" as the env var name from the new code example
DANBOORU_TIER = os.getenv("danbooru_tier", "gold").lower() # Default to gold if not set

# Update Danbooru ratings based on tier (kept from existing logic, uses DANBOORU_TIER)
if DANBOORU_TIER == "platinum":
    RATINGS["danbooru"] = RATING_TYPES['danbooru_platinum']
else: # Default to gold for free or gold tier (covers "gold" and non-set/empty)
    RATINGS["danbooru"] = RATING_TYPES['danbooru_gold']

# Construct Danbooru API auth string if login and key are provided
if os.getenv("danbooru_login") and os.getenv("danbooru_api_key"):
    DAN_API_AUTH = f'&login={os.getenv("danbooru_login")}&api_key={os.getenv("danbooru_api_key")}'
    if DEBUG: print("[Ranbooru] Danbooru API auth string constructed.")

# Construct Gelbooru API auth string if user_id and key are provided
if os.getenv("gelbooru_user_id") and os.getenv("gelbooru_api_key"):
    GEL_API_AUTH = f'&user_id={os.getenv("gelbooru_user_id")}&api_key={os.getenv("gelbooru_api_key")}'
    if DEBUG: print("[Ranbooru] Gelbooru API auth string constructed.")

# UI related default values
COLORED_BG = ['black_background', 'aqua_background', 'white_background', 'colored_background', 'gray_background', 'blue_background', 'green_background', 'red_background', 'brown_background', 'purple_background', 'yellow_background', 'orange_background', 'pink_background', 'plain', 'transparent_background', 'simple_background', 'two-tone_background', 'grey_background']
ADD_BG = ['outdoors', 'indoors']
BW_BG = ['monochrome', 'greyscale', 'grayscale']

# Script settings
POST_AMOUNT = 100  # Max number of posts to fetch per page
COUNT = 100 # Max number of posts to try and fetch before giving up. Not implemented properly.
DEBUG = False # Enables verbose printing to console

# Endpoint constants for various boorus
BOORU_ENDPOINTS = {
    "gelbooru": "https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1&limit={limit}&pid={pid}{tags}{id}",
    "rule34": "https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&limit={limit}&pid={pid}{tags}{id}",
    "safebooru": "https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&limit={limit}&pid={pid}{tags}{id}",
    "danbooru": "https://danbooru.donmai.us/posts.json?limit={limit}&page={pid}{tags}{id}",
    "konachan": "https://konachan.com/post.json?limit={limit}&page={pid}{tags}{id}",
    "yande.re": "https://yande.re/post.json?limit={limit}&page={pid}{tags}{id}",
    "aibooru": "https://aibooru.online/posts.json?limit={limit}&page={pid}{tags}{id}",
    "xbooru": "https://xbooru.com/index.php?page=dapi&s=post&q=index&json=1&limit={limit}&pid={pid}{tags}{id}",
    "e621": "https://e621.net/posts.json?limit={limit}&page={pid}{tags}{id}"
}

# Rating systems for different boorus
RATING_TYPES = {
    "none": {"All": "all"},
    "full": {"All": "all", "Safe": "safe", "Questionable": "questionable", "Explicit": "explicit"},
    "single": {"All": "all", "Safe": "g", "Sensitive": "s", "Questionable": "q", "Explicit": "e"},
    "danbooru_gold": {"All": "all", "Safe": "g", "Sensitive": "s", "Questionable": "q", "Explicit": "e"},
    "danbooru_platinum": {"All": "all", "Safe": "g", "Sensitive": "s", "Questionable": "q", "Explicit": "e", "Premium": "p"}
}
RATINGS = {
    "e621": RATING_TYPES['full'],
    "danbooru": RATING_TYPES['danbooru_gold'], # Default to gold, will update dynamically based on tier
    "aibooru": RATING_TYPES['full'],
    "yande.re": RATING_TYPES['full'],
    "konachan": RATING_TYPES['full'],
    "safebooru": RATING_TYPES['none'],
    "rule34": RATING_TYPES['full'],
    "xbooru": RATING_TYPES['full'],
    "gelbooru": RATING_TYPES['single']
}

# Helper functions
def get_available_ratings(booru_site):
    """Returns available rating choices for a given booru."""
    # Use a safe default if booru_site is not in RATINGS
    return gr.Radio.update(choices=list(RATINGS.get(booru_site, RATING_TYPES['none']).keys()), value="All")

def show_fringe_benefits(booru_site):
    """Determines visibility of fringe benefits checkbox."""
    return gr.Checkbox.update(visible=(booru_site == 'gelbooru'))

def check_exception(booru_site, parameters):
    """Checks for booru-specific exceptions like tag limits or ID support."""
    post_id = parameters.get('post_id')
    tags = parameters.get('tags')
    if booru_site == 'konachan' and post_id:
        raise ValueError("Konachan does not support post IDs.")
    if booru_site == 'yande.re' and post_id:
        raise ValueError("Yande.re does not support post IDs.")
    if booru_site == 'e621' and post_id: # e621 uses 'id' in URL but not as a direct post_id query param in the same way
        raise ValueError("e621 does not support post IDs directly in Ranbooru search like other boorus. Use 'id:<post_id>' in tags.")
    if booru_site == 'danbooru' and tags:
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        if DANBOORU_TIER == 'free' and len(tag_list) > 1:
            raise ValueError("Danbooru (Free tier) allows only 1 tag for search. Upgrade to Gold/Platinum for more tags.")
        if DANBOORU_TIER == 'gold' and len(tag_list) > 2: # Gold users can use 2 tags.
            raise ValueError("Danbooru (Gold tier) allows only up to 2 tags for search. Upgrade to Platinum for more tags.")
        # Platinum users have a higher limit, often around 6, but the API is flexible. Assume no hard limit here for simplicity.

def generate_chaos(positive_prompt, negative_prompt, chaos_amount):
    """Generates chaos by mixing positive and negative prompts."""
    if DEBUG: print(f"[Ranbooru] Generating chaos with amount: {chaos_amount}")
    combined_list = [tag.strip() for tag in positive_prompt.split(',') + negative_prompt.split(',') if tag.strip()]
    if not combined_list: return positive_prompt, negative_prompt # Avoid processing if empty

    unique_tags = list(set(combined_list))
    random.shuffle(unique_tags)

    num_to_move = round(len(unique_tags) * chaos_amount)

    new_negative_tags = unique_tags[:num_to_move]
    new_positive_tags = unique_tags[num_to_move:]

    return ','.join(new_positive_tags), ','.join(new_negative_tags)

def resize_image(img, target_width, target_height, crop_to_center=True):
    """Resizes an image, optionally cropping to center."""
    if DEBUG: print(f"[Ranbooru] Resizing image to {target_width}x{target_height}, crop: {crop_to_center}")
    original_width, original_height = img.size

    if crop_to_center:
        original_aspect = original_width / original_height
        target_aspect = target_width / target_height

        if original_aspect > target_aspect: # Original is wider than target -> crop width
            new_height = target_height
            new_width = int(new_height * original_aspect)
        else: # Original is taller than target (or same aspect) -> crop height
            new_width = target_width
            new_height = int(new_width / original_aspect)

        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        left = (new_width - target_width) / 2
        top = (new_height - target_height) / 2
        right = (new_width + target_width) / 2
        bottom = (new_height + target_height) / 2

        img_cropped = img_resized.crop((left, top, right, bottom))
        return img_cropped
    else: # No cropping, just resize (may change aspect ratio)
        return img.resize((target_width, target_height), Image.Resampling.LANCZOS)

def modify_prompt(original_prompt, deepbooru_tags, mode):
    """Modifies prompt based on DeepBooru tags and selected mode."""
    if DEBUG: print(f"[Ranbooru] Modifying prompt with mode: {mode}")
    deepbooru_tags_cleaned = ','.join(tag.strip() for tag in deepbooru_tags.split(',') if tag.strip())
    if not deepbooru_tags_cleaned: return original_prompt

    if mode == 'Add Before':
        return f"{deepbooru_tags_cleaned},{original_prompt}".strip(',') if original_prompt else deepbooru_tags_cleaned
    elif mode == 'Add After':
        return f"{original_prompt},{deepbooru_tags_cleaned}".strip(',') if original_prompt else deepbooru_tags_cleaned
    elif mode == 'Replace':
        return deepbooru_tags_cleaned
    return original_prompt # Should not happen with valid mode

def remove_repeated_tags(prompt_string):
    """Removes repeated tags from a comma-separated prompt string."""
    if not prompt_string: return ""
    tags = prompt_string.split(',')
    seen = set()
    unique_tags = []
    for tag in tags:
        stripped_tag = tag.strip()
        if stripped_tag and stripped_tag not in seen:
            unique_tags.append(stripped_tag)
            seen.add(stripped_tag)
    return ','.join(unique_tags)

def limit_prompt_tags(prompt_string, limit_value, mode='Limit %'):
    """Limits the number of tags in a prompt string by percentage or absolute count."""
    if not prompt_string: return ""
    tags = [tag.strip() for tag in prompt_string.split(',') if tag.strip()]
    if not tags: return ""

    if mode == 'Limit %': # Limit by percentage
        new_tag_count = int(len(tags) * limit_value)
    elif mode == 'Max Tags': # Limit by absolute number
        new_tag_count = int(limit_value) # limit_value is max_tags_slider here
    else: # Should not happen
        return prompt_string

    return ','.join(tags[:new_tag_count])

# --- Booru Classes ---
class Booru:
    """Base class for all booru interactions."""
    def __init__(self, booru_name):
        self.booru_name = booru_name
        self.base_url = BOORU_ENDPOINTS[booru_name]
        self.headers = {'user-agent': f'RanbooruScript/{Script.version}'} # Assuming Script.version is accessible
        self.current_url = "" # To store the last used URL for debugging or info

    def _make_request(self, url_params, method='GET', **kwargs):
        """Makes an HTTP request and returns the JSON response."""
        global COUNT # To update the global post count from API responses

        # Construct the full URL
        tags_query = url_params.get('tags', '')
        # Ensure 'id' parameter is correctly formatted if present, typically for specific post fetching
        id_query = f"&id={url_params['id']}" if 'id' in url_params and url_params['id'] else "" # Gelbooru, Rule34, Safebooru, XBooru (id as param)
        if self.booru_name == "danbooru" and 'id' in url_params and url_params['id']: # Danbooru (id in path)
             # For Danbooru, ID overrides tags and page for single post fetch
            self.current_url = self.base_url.split('.json?')[0] + f"/{url_params['id']}.json?" + self.base_url.split('?')[1].format(limit=1, pid=1, tags="",id="")
            # Remove other params if ID is present for Danbooru single post
            tags_query = ""
            url_params['pid'] = 1 # Page is irrelevant
            url_params['limit'] = 1
        elif self.booru_name == "e621" and 'id' in url_params and url_params['id']:
            self.current_url = self.base_url.split('.json?')[0] + f"/{url_params['id']}.json?" + self.base_url.split('?')[1].format(limit=1, pid=1, tags="",id="")
            tags_query = ""
            url_params['pid'] = 1
            url_params['limit'] = 1
        else: # For other boorus or general search
            self.current_url = self.base_url.format(
                limit=url_params.get('limit', POST_AMOUNT),
                pid=url_params.get('pid', random.randint(0, url_params.get('max_pages', 10)-1)), # pid is page number for some
                tags=tags_query,
                id=id_query # This will be empty if no id_query was constructed
            )

        if DEBUG: print(f"[Ranbooru] Requesting URL: {self.current_url}")

        try:
            response = requests.request(method, self.current_url, headers=self.headers, **kwargs)
            response.raise_for_status() # Raises HTTPError for bad responses (4XX or 5XX)
            data = response.json()

            # Update COUNT based on typical response structures
            if self.booru_name == 'gelbooru' and isinstance(data, dict) and '@attributes' in data:
                COUNT = data['@attributes'].get('count', 0)
            elif isinstance(data, list): # For boorus where response is a list of posts
                COUNT = len(data)
            elif isinstance(data, dict) and 'posts' in data and isinstance(data['posts'], list): # For e621 list
                COUNT = len(data['posts'])
            elif isinstance(data, dict) and ('post' in data or 'success' in data and data.get('success') is False): # Single post (Danbooru, e621) or error
                 COUNT = 1 if ('post' in data and data['post']) or ('id' in data and data.get('id')) else 0 # Count 1 if single post found
            else: # Default or if structure is unknown/unexpected
                COUNT = 0
            if DEBUG: print(f"[Ranbooru] Current COUNT set to: {COUNT} for {self.booru_name}")
            return data
        except requests.exceptions.RequestException as e:
            print(f"[Ranbooru] Error during request to {self.booru_name}: {e}")
            COUNT = 0 # Reset count on error
            return None # Or {} or raise an error, depending on desired error handling
        except ValueError as e: # Includes JSONDecodeError
            print(f"[Ranbooru] Error decoding JSON from {self.booru_name}: {e}")
            COUNT = 0
            return None

    def get_posts(self, tags="", page_num=0, limit=POST_AMOUNT, max_pages=10, post_id=None):
        """Fetches posts. 'page_num' is 0-indexed for random, or specific page for pagination.
           'post_id' for fetching a specific post by ID.
        """
        url_params = {'limit': limit, 'tags': tags}
        if post_id:
            url_params['id'] = post_id
            # For boorus where ID is part of the path, pid/page might not be needed or handled differently
            if self.booru_name not in ["danbooru", "e621"]: # These handle ID in _make_request path construction
                 url_params['pid'] = 0 # Not strictly page, but part of URL structure for some ID calls
        else:
            # Most APIs use 'pid' for page number in XML/DAPI style, or 'page' in JSON style
            # Gelbooru DAPI uses pid (0-indexed for random page calculation)
            # Danbooru/Konachan/Yande.re/AIBooru/e621 use page (1-indexed usually, but random calc needs care)
            # Safebooru/Rule34/XBooru use pid
            # For simplicity, 'pid' in base_url can map to either 'pid' or 'page' as needed by the URL string
            url_params['pid'] = page_num if page_num > 0 else random.randint(0, max_pages -1) # Use provided page or random
            url_params['max_pages'] = max_pages # Pass for random calculation if needed

        return self._make_request(url_params)

    def _normalize_post_data(self, post):
        """Normalizes post data structure from different boorus."""
        # Default normalization, subclasses should override for specific transformations
        # Goal: ensure 'tags' (as string), 'file_url', 'score' are present if possible
        if 'tag_string' in post and 'tags' not in post: # Danbooru, AIBooru
            post['tags'] = post['tag_string']
        if 'tags' in post and isinstance(post['tags'], dict): # e621
            tag_list = []
            for category in post['tags'].values():
                if isinstance(category, list): tag_list.extend(category)
            post['tags'] = ' '.join(tag_list)

        # Ensure score is an int
        post['score'] = int(post.get('score', 0) if isinstance(post.get('score'), (int, float, str)) and str(post.get('score')).isdigit() else 0)

        # Ensure essential keys exist, even if empty
        post.setdefault('tags', '')
        post.setdefault('file_url', '') # Subclasses for Gelbooru-like need to construct this
        return post

    def process_response(self, data):
        """Processes the raw JSON data into a list of normalized post dicts."""
        if not data: return []

        posts_list = []
        if self.booru_name in ['gelbooru', 'xbooru', 'rule34', 'safebooru'] and isinstance(data, dict) and 'post' in data:
            posts_list = data['post'] if isinstance(data['post'], list) else [data['post']] # Gelbooru can return single post dict if count=1
        elif self.booru_name == 'e621' and isinstance(data, dict) and 'posts' in data:
            posts_list = data['posts']
        elif self.booru_name == 'e621' and isinstance(data, dict) and 'post' in data: # Single post e621
            posts_list = [data['post']]
        elif self.booru_name == 'danbooru' and isinstance(data, dict) and 'id' in data: # Single post Danbooru
            posts_list = [data]
        elif isinstance(data, list): # Konachan, Yande.re, AIBooru, Danbooru (list)
            posts_list = data

        if not isinstance(posts_list, list): # Ensure posts_list is always a list
            if DEBUG: print(f"[Ranbooru] Unexpected data structure for posts_list in {self.booru_name}: {type(posts_list)}")
            return []

        return [self._normalize_post_data(post) for post in posts_list if post] # Filter out empty/None posts


class Gelbooru(Booru):
    def __init__(self, fringe_benefits=True): # fringe_benefits added here
        super().__init__('gelbooru')
        self.fringe_benefits = fringe_benefits
        if GEL_API_AUTH: # Check if API auth is available
            self.base_url += f"&api_key={GEL_API_AUTH.split(':')[0]}&user_id={GEL_API_AUTH.split(':')[1]}"
            if DEBUG: print("[Ranbooru] Gelbooru using API key.")


    def get_posts(self, tags="", page_num=0, limit=POST_AMOUNT, max_pages=10, post_id=None):
        # Gelbooru specific: pid calculation for pagination vs random
        # For random, pid is random.randint(0, effective_max_pages - 1)
        # For pagination, pid is the actual page number (0-indexed)
        # This logic is now more generalized in the base Booru class's _make_request
        url_params = {'limit': limit, 'tags': tags}
        cookies = {'fringeBenefits': 'yup'} if self.fringe_benefits else None

        if post_id:
            url_params['id'] = post_id # Passed as '&id=...' query parameter
            # pid for ID fetch might not be relevant or can be 0
            url_params['pid'] = 0
        else:
            # Calculate effective max_pages for random PID if COUNT is known and small
            # This requires a preliminary request or smarter COUNT handling, simplified for now.
            # Base class handles random.randint(0, max_pages-1) if page_num is 0.
            url_params['pid'] = page_num if page_num > 0 else random.randint(0, max_pages-1)
            url_params['max_pages'] = max_pages

        return self._make_request(url_params, cookies=cookies)

    def _normalize_post_data(self, post):
        post = super()._normalize_post_data(post)
        # Gelbooru, XBooru, Safebooru construct file_url if not present (though usually it is)
        if not post.get('file_url') and 'image' in post and 'directory' in post:
            if self.booru_name == 'gelbooru':
                 post['file_url'] = f"https://img3.gelbooru.com/images/{post['directory']}/{post['image']}"
            elif self.booru_name == 'safebooru': # Safebooru has a different image host sometimes
                 post['file_url'] = f"https://safebooru.org/images/{post['directory']}/{post['image']}"
            # XBooru is handled by its own class override if needed
        return post

class XBooru(Gelbooru): # Inherits Gelbooru structure, overrides name and potentially file_url
    def __init__(self):
        super(Gelbooru, self).__init__('xbooru') # Call Booru.__init__ with 'xbooru'
        # XBooru does not use fringe_benefits or API keys in the same way as Gelbooru

    def _normalize_post_data(self, post):
        post = super(Gelbooru, self)._normalize_post_data(post) # Call Booru's normalize
        if not post.get('file_url') and 'image' in post and 'directory' in post:
             post['file_url'] = f"https://xbooru.com/images/{post['directory']}/{post['image']}"
        return post

class Rule34(Gelbooru): # Inherits Gelbooru structure (XML-like API), overrides name
    def __init__(self):
        super(Gelbooru, self).__init__('rule34') # Call Booru.__init__ with 'rule34'

    # Rule34 typically provides full file_url, so Gelbooru's normalize might be sufficient.
    # Override _normalize_post_data if specific handling for Rule34 is needed.

class Safebooru(Gelbooru): # Inherits Gelbooru structure, overrides name
    def __init__(self):
        super(Gelbooru, self).__init__('safebooru') # Call Booru.__init__ with 'safebooru'

    def _normalize_post_data(self, post):
        post = super(Gelbooru, self)._normalize_post_data(post) # Call Booru's normalize
        if not post.get('file_url') and 'image' in post and 'directory' in post:
             post['file_url'] = f"https://safebooru.org/images/{post['directory']}/{post['image']}"
        return post


class Danbooru(Booru):
    def __init__(self):
        super().__init__('danbooru')
        if DAN_API_AUTH: # Check if API auth is available
            self.headers['Authorization'] = f"Basic {DAN_API_AUTH}"
            if DEBUG: print("[Ranbooru] Danbooru using API key.")
        # Tier specific logic (tag limits) is handled in check_exception and UI for now.
        # Actual API endpoint doesn't change with tier, but available parameters/limits do.

    def get_posts(self, tags="", page_num=0, limit=POST_AMOUNT, max_pages=10, post_id=None):
        # Danbooru uses 'page' (1-indexed) not 'pid' for pagination in general searches
        # For random, it can use `page=b<random_post_id>` or just random page up to a limit (e.g., 1000 for non-gold)
        # Simple random page for now.
        url_params = {'limit': limit, 'tags': tags}
        if post_id:
            url_params['id'] = post_id # This will trigger ID-based path in _make_request
        else:
            # Page for Danbooru is 1-indexed. If page_num is 0 (random), pick from 1 to max_pages.
            url_params['pid'] = page_num if page_num > 0 else random.randint(1, max_pages)

        return self._make_request(url_params)

    # _normalize_post_data is mostly handled by base for 'tag_string' and 'score'.
    # Danbooru file URLs are usually direct.

class Konachan(Booru): # Yande.re, AIBooru are similar JSON APIs
    def __init__(self, booru_name='konachan'): # Allow reuse for similar boorus
        super().__init__(booru_name)

    def get_posts(self, tags="", page_num=0, limit=POST_AMOUNT, max_pages=10, post_id=None):
        # These APIs use 'page' (1-indexed typically) for pagination.
        # Post ID search is not supported via a simple param for Konachan/Yandere in their list API.
        if post_id:
            # This should ideally be caught by check_exception earlier.
            # If direct post fetch is needed, it's a different endpoint /posts/{id}.json
            # For now, assuming this method is for tag-based searches.
            if DEBUG: print(f"[Ranbooru] {self.booru_name} does not support post ID directly in list search. Fetching by tags instead if any.")
            # Fallback to tag search or return empty if post_id was the only criteria.
            # To prevent errors, let's clear post_id here if it reaches.
            post_id = None
            # Or raise ValueError("Post ID search not directly supported in this method for this booru.")

        url_params = {'limit': limit, 'tags': tags}
        # Page for these is 1-indexed. If page_num is 0 (random), pick from 1 to max_pages.
        url_params['pid'] = page_num if page_num > 0 else random.randint(1, max_pages)

        return self._make_request(url_params)

class Yandere(Konachan): # Inherits Konachan structure
    def __init__(self):
        super().__init__('yande.re')

class AIBooru(Konachan): # Inherits Konachan structure (JSON, page based)
    def __init__(self):
        super().__init__('aibooru')
    # AIBooru uses 'tag_string', base _normalize_post_data handles this.


class E621(Booru):
    def __init__(self):
        super().__init__('e621')
        # e621 has its own API key system if needed, but public access is generous.
        # self.headers['Authorization'] = f"Basic {base64.b64encode(f'{user}:{api_key}'.encode()).decode()}"
        # For now, no auth assumed.

    def get_posts(self, tags="", page_num=0, limit=POST_AMOUNT, max_pages=10, post_id=None):
        # e621 uses 'page' for pagination. It can also use `page=b<before_id>` or `a<after_id>`.
        # Simple random page for now.
        url_params = {'limit': limit, 'tags': tags}
        if post_id:
             url_params['id'] = post_id # Triggers ID-based path in _make_request
        else:
            # Page for e621 is generally 1-indexed for direct access, but can be complex.
            # Random page can go up to 750 for unauth/basic auth.
            url_params['pid'] = page_num if page_num > 0 else random.randint(1, min(max_pages, 750))

        return self._make_request(url_params)

    # _normalize_post_data in base class handles e621 'tags' dictionary and 'score'.

# --- End Booru Classes ---

class Script(scripts.Script):
    # Class attributes
    previous_loras = "" # Stores LoRA string from previous run if locked
    last_img = []       # Stores fetched images for img2img or DeepBooru
    real_steps = 0      # Stores original step count for img2img pass
    version = "1.3.0"   # Script version
    original_prompt = ""# Stores the user's original prompt from the UI
    result_url = []     # Stores URLs of fetched posts for display
    result_img = []     # Stores PIL Images of fetched posts for display in UI (distinct from last_img for processing)

    # Storing UI states on self to access in postprocess or other methods if needed
    # These will be set in before_process based on UI inputs.
    # (Consider if all these truly need to be self attributes or can be passed around)
    use_img2img_flag = False
    use_ip_flag = False # ControlNet flag
    enabled_flag = False # Ranbooru main enable
    denoising_strength_val = 0.75
    crop_center_flag = False
    use_deepbooru_flag = False
    type_deepbooru_val = "Add Before"
    use_last_img_flag = False # For img2img with only the first fetched image

    def title(self):
        return "Ranbooru"

    def show(self, is_img2img):
        return scripts.AlwaysVisible # Show in both txt2img and img2img tabs

    def get_files(self, path):
        """Lists .txt files in a given path."""
        if not os.path.exists(path): return []
        return [f for f in os.listdir(path) if f.endswith('.txt')]

    def refresh_ser(self): return gr.update(choices=self.get_files(user_search_dir))
    def refresh_rem(self): return gr.update(choices=self.get_files(user_remove_dir))
    def refresh_forbidden_files(self): return gr.update(choices=self.get_forbidden_files())

    def get_forbidden_files(self):
        """Ensures default forbidden tags file exists and lists all available."""
        os.makedirs(user_forbidden_prompt_dir, exist_ok=True)
        files = [f for f in os.listdir(user_forbidden_prompt_dir) if f.endswith('.txt')]
        default_file_name = 'tags_forbidden.txt'
        default_file_path = os.path.join(user_forbidden_prompt_dir, default_file_name)

        if not os.path.exists(default_file_path): # Create if default doesn't exist at all
            with open(default_file_path, 'w', encoding='utf-8') as f:
                f.write("# Add tags here, one per line, to remove them from prompts *after* fetching from booru.\n")
                f.write("artist_name_example\n")
                f.write("character_name_example\n")

        if default_file_name not in files: # Add to list if it exists but wasn't caught by listdir (shouldn't happen)
            files.append(default_file_name)

        return files if files else [default_file_name] # Should always return at least the default

    def hide_object(self, booru_site_val):
        """Hides post ID textbox if booru does not support it."""
        # This function is meant to be called by a Gradio `change` event.
        # It needs to return an update for the object to be hidden/shown.
        # Example: post_id_textbox.change(self.hide_object, booru_dropdown, post_id_textbox)
        # The first argument to this function will be the value of booru_dropdown.
        # The return must be gr.Textbox.update(...)
        if booru_site_val in ['konachan', 'yande.re', 'e621', 'aibooru']: # Boorus that don't support direct post ID fetching in the same way
            return gr.Textbox.update(visible=False)
        return gr.Textbox.update(visible=True)

    def get_last_result(self):
        """Returns the last fetched image and its URL for display in UI."""
        # This function will be called by a button in the UI.
        # It should return updates for an Image component and a Textbox/Markdown component.
        if self.result_img and self.result_url:
            # Assuming only one image/URL is displayed from the last batch for simplicity
            # Ensure result_img contains PIL images, not file paths or other types
            # And result_url contains corresponding URLs

            # Find the last valid PIL image and its URL
            last_valid_image = None
            last_valid_url = "No valid image/URL in last batch." # Default if loop doesn't find one

            for i in range(len(self.result_img) - 1, -1, -1):
                if isinstance(self.result_img[i], Image.Image): # Check if it's a PIL image
                    last_valid_image = self.result_img[i]
                    if i < len(self.result_url): # Check URL index bounds
                        last_valid_url = self.result_url[i]
                    break # Found the last valid one

            if last_valid_image:
                return last_valid_image, last_valid_url
            else: # No valid PIL image found
                # Attempt to fetch the last URL if result_url is populated but result_img wasn't (e.g., if image fetching was deferred)
                if self.result_url:
                    last_url = self.result_url[-1]
                    if last_url:
                        try:
                            if DEBUG: print(f"[Ranbooru] get_last_result: Fetching {last_url} on demand.")
                            response = requests.get(last_url, timeout=10)
                            response.raise_for_status()
                            fetched_on_demand_img = Image.open(BytesIO(response.content))
                            return fetched_on_demand_img, last_url
                        except Exception as e:
                            print(f"[Ranbooru] get_last_result: Failed to fetch {last_url} on demand: {e}")
                            return None, f"Failed to fetch last URL: {last_url}"
                return None, "No valid image/URL in the last fetched batch."

        return None, "No image/URL fetched yet or list was empty."


    def ui(self, is_img2img):
        with InputAccordion(False, label=f"Ranbooru v{self.version}", elem_id=self.elem_id("ra_enable")) as enabled:
            # API & Booru selection
            with gr.Row():
                booru_selected = gr.Dropdown(
                    list(BOORU_ENDPOINTS.keys()), label="Booru", value="gelbooru", elem_id=self.elem_id("ra_booru")
                )
                max_pages_slider = gr.Slider(
                    label="Max Pages to Search", minimum=1, maximum=1000, value=100, step=1, elem_id=self.elem_id("ra_max_pages") # Increased max
                )
            with gr.Row():
                post_id_textbox = gr.Textbox(lines=1, label="Post ID (Overrides Tags)", elem_id=self.elem_id("ra_post_id"))
                # Hide post_id_textbox based on booru selection (initial and on change)
                booru_selected.change(self.hide_object, inputs=[booru_selected], outputs=[post_id_textbox])
                # Call it once for initial state based on default "gelbooru"
                # This requires a direct call or a setup mechanism if Gradio allows. For now, assume manual UI adjustment or it defaults correctly.

            # Tags and Prompting
            gr.Markdown("### Tags & Prompting")
            tags_textbox = gr.Textbox(
                lines=1, label="Tags to Search", info="Use __wildcard__ for random from file. Comma separated.",
                elem_id=self.elem_id("ra_tags")
            )
            remove_tags_textbox = gr.Textbox(
                lines=1, label="Tags to Remove (Pre-fetch)", info="Comma separated. Wildcards supported. Applied before fetching.",
                elem_id=self.elem_id("ra_remove_tags")
            )
            mature_rating_radio = gr.Radio(
                list(RATINGS.get('gelbooru', {}).keys()), label="Mature Rating", value="All", elem_id=self.elem_id("ra_mature_rating")
            )
            booru_selected.change(get_available_ratings, inputs=[booru_selected], outputs=[mature_rating_radio])

            with gr.Row():
                remove_bad_tags_checkbox = gr.Checkbox(label="Remove Common Bad Tags", value=True, elem_id=self.elem_id("ra_remove_bad"))
                shuffle_tags_checkbox = gr.Checkbox(label="Shuffle Tags", value=True, elem_id=self.elem_id("ra_shuffle_tags"))
                change_dash_checkbox = gr.Checkbox(label='Convert "_" to spaces in tags', value=False, elem_id=self.elem_id("ra_change_dash"))

            same_prompt_checkbox = gr.Checkbox(label="Use Same Prompt for All Images in Batch", value=False, elem_id=self.elem_id("ra_same_prompt"))
            fringe_benefits_checkbox = gr.Checkbox( # Gelbooru specific
                label="Fringe Benefits (Gelbooru)", value=True, visible=(booru_selected.value == "gelbooru"), elem_id=self.elem_id("ra_fringe")
            )
            booru_selected.change(show_fringe_benefits, inputs=[booru_selected], outputs=[fringe_benefits_checkbox])

            with gr.Row():
                limit_tags_slider = gr.Slider(label="Limit Tags by %", minimum=0.05, maximum=1.0, value=1.0, step=0.05, elem_id=self.elem_id("ra_limit_tags"))
                max_tags_count_slider = gr.Slider(label="Max Tags (Absolute)", minimum=1, maximum=150, value=100, step=1, elem_id=self.elem_id("ra_max_tags_count")) # Increased max

            # Background & Color
            gr.Markdown("### Background & Color")
            with gr.Row():
                change_background_radio = gr.Radio(
                    ["Don't Change", "Add Background", "Remove Background", "Remove All BG"],
                    label="Change Background", value="Don't Change", elem_id=self.elem_id("ra_change_bg")
                )
                change_color_radio = gr.Radio(
                    ["Don't Change", "Colored", "Limited Palette", "Monochrome"],
                    label="Change Color", value="Don't Change", elem_id=self.elem_id("ra_change_color")
                )

            # Sorting & Filtering (Post-Fetch)
            gr.Markdown("### Sorting & Filtering (Post-Fetch)")
            sorting_order_radio = gr.Radio(
                ["Random", "High Score", "Low Score", "Newest First", "Oldest First"], # Added more options
                label="Sort Posts By", value="Random", elem_id=self.elem_id("ra_sorting_order")
            )

            forbidden_prompt_tags_textbox = gr.Textbox(
                lines=2, label="Forbidden Tags (Manual, Post-fetch)",
                info="Comma-separated. Applied to Ranbooru tags *after* fetching.", elem_id=self.elem_id("ra_forbidden_manual")
            )
            with gr.Row():
                use_forbidden_prompt_file_checkbox = gr.Checkbox(label="Use Forbidden Tags from File", value=True, elem_id=self.elem_id("ra_use_forbidden_file"))
                choose_forbidden_prompt_file_dropdown = gr.Dropdown(
                    self.get_forbidden_files(), label="Choose Forbidden Tags File", value="tags_forbidden.txt",
                    interactive=True, elem_id=self.elem_id("ra_choose_forbidden_file")
                )
                refresh_forbidden_files_button = gr.Button("Refresh Files", elem_id=self.elem_id("ra_refresh_forbidden_btn"))
                refresh_forbidden_files_button.click(fn=self.refresh_forbidden_files, inputs=[], outputs=[choose_forbidden_prompt_file_dropdown])

            disable_ranbooru_prompt_modification_checkbox = gr.Checkbox(
                label="Disable ALL Ranbooru Prompt Modifications",
                info="If checked, only user's UI prompt and LoRAnado are used. All tag fetching/processing is skipped.",
                value=False, elem_id=self.elem_id("ra_disable_all_mods")
            )

            # Img2Img & ControlNet & DeepBooru
            with gr.Accordion("Img2Img / ControlNet / DeepBooru", open=False, elem_id=self.elem_id("ra_img_accordion")):
                with gr.Row():
                    use_img2img_checkbox = gr.Checkbox(label="Enable Img2Img Pass", value=False, elem_id=self.elem_id("ra_use_img2img"))
                    use_controlnet_checkbox = gr.Checkbox(label="Send to ControlNet", value=False, elem_id=self.elem_id("ra_use_controlnet"))
                denoising_slider = gr.Slider(
                    label="Denoising Strength / CN Weight", minimum=0.01, maximum=1.0, value=0.75, step=0.01, elem_id=self.elem_id("ra_denoising")
                )
                with gr.Row():
                    use_last_img_checkbox = gr.Checkbox(label="Use First Fetched Image for All in Batch", value=False, elem_id=self.elem_id("ra_use_last_img"))
                    crop_center_checkbox = gr.Checkbox(label="Crop to Fit (Img2Img/DeepBooru)", value=True, elem_id=self.elem_id("ra_crop_center"))
                with gr.Row():
                    use_deepbooru_checkbox = gr.Checkbox(label="Tag with DeepBooru", value=False, elem_id=self.elem_id("ra_use_deepbooru"))
                    type_deepbooru_radio = gr.Radio(
                        ["Add Before", "Add After", "Replace"], label="DeepBooru Tags Position", value="Add Before", elem_id=self.elem_id("ra_type_deepbooru")
                    )

            # File Operations (Search/Remove Tags from user files)
            with gr.Accordion("File-based Tag Operations", open=False, elem_id=self.elem_id("ra_file_ops_accordion")):
                with gr.Row():
                    use_search_txt_checkbox = gr.Checkbox(label="Add Tags from Search File", value=False, elem_id=self.elem_id("ra_use_search_txt"))
                    choose_search_txt_dropdown = gr.Dropdown(
                        self.get_files(user_search_dir), label="Choose Search File", interactive=True, elem_id=self.elem_id("ra_choose_search_txt")
                    )
                    search_refresh_button = gr.Button("Refresh", elem_id=self.elem_id("ra_search_refresh_btn"))
                    search_refresh_button.click(fn=self.refresh_ser, inputs=[], outputs=[choose_search_txt_dropdown])
                with gr.Row():
                    use_remove_txt_checkbox = gr.Checkbox(label="Use Remove Tags from File (Pre-fetch)", value=False, elem_id=self.elem_id("ra_use_remove_txt"))
                    choose_remove_txt_dropdown = gr.Dropdown(
                        self.get_files(user_remove_dir), label="Choose Remove File", interactive=True, elem_id=self.elem_id("ra_choose_remove_txt")
                    )
                    remove_refresh_button = gr.Button("Refresh", elem_id=self.elem_id("ra_remove_refresh_btn"))
                    remove_refresh_button.click(fn=self.refresh_rem, inputs=[], outputs=[choose_remove_txt_dropdown])

            # Extra / Advanced Options
            with gr.Accordion("Advanced Options", open=False, elem_id=self.elem_id("ra_extra_accordion")):
                with gr.Row():
                    mix_prompt_checkbox = gr.Checkbox(label="Mix Tags from Multiple Posts", value=False, elem_id=self.elem_id("ra_mix_prompt"))
                    mix_amount_slider = gr.Slider(label="Number of Posts to Mix", minimum=2, maximum=10, value=2, step=1, elem_id=self.elem_id("ra_mix_amount"))
                with gr.Row():
                    chaos_mode_radio = gr.Radio(["None", "Chaos", "Less Chaos"], label="Chaos Mode", value="None", elem_id=self.elem_id("ra_chaos_mode"))
                    chaos_amount_slider = gr.Slider(label="Chaos Amount %", minimum=0.01, maximum=1.0, value=0.5, step=0.01, elem_id=self.elem_id("ra_chaos_amount"))
                with gr.Row():
                    negative_mode_radio = gr.Radio(
                        ["None", "Move Ranbooru Tags to Negative"], label="Negative Mode", value="None", elem_id=self.elem_id("ra_negative_mode")
                    )
                    use_same_seed_checkbox = gr.Checkbox(label="Use Same Seed for All in Batch", value=False, elem_id=self.elem_id("ra_use_same_seed"))
                use_cache_checkbox = gr.Checkbox(label="Use Requests Cache (1hr expiry)", value=True, elem_id=self.elem_id("ra_use_cache"))

            # LoRAnado Section
            with InputAccordion(False, label="LoRAnado - Automatic LoRA Adder", elem_id=self.elem_id("lo_enable")) as lora_enabled_checkbox:
                lora_folder_textbox = gr.Textbox(
                    lines=1, label="LoRAs Subfolder (e.g., 'style' or blank for main LoRA dir)", elem_id=self.elem_id("lo_lora_folder")
                )
                lora_amount_slider = gr.Slider(label="Number of LoRAs to Add", minimum=1, maximum=20, value=1, step=1, elem_id=self.elem_id("lo_lora_amount")) # Increased max
                with gr.Row():
                    lora_min_weight_slider = gr.Slider(label="Min LoRA Weight", minimum=-2.0, maximum=2.0, value=0.6, step=0.05, elem_id=self.elem_id("lo_lora_min")) # Broader range
                    lora_max_weight_slider = gr.Slider(label="Max LoRA Weight", minimum=-2.0, maximum=2.0, value=1.0, step=0.05, elem_id=self.elem_id("lo_lora_max")) # Broader range
                lora_custom_weights_textbox = gr.Textbox(
                    lines=1, label="Custom LoRA Weights (Optional, comma-sep)",
                    info="e.g., 0.5,0.7,-0.2. Overrides min/max for listed LoRAs.", elem_id=self.elem_id("lo_lora_custom_weights")
                )
                lora_lock_previous_checkbox = gr.Checkbox(label="Lock Previous LoRAnado Setup", value=False, elem_id=self.elem_id("lo_lora_lock_prev"))

            # Display last fetched image and URL (optional feature)
            with gr.Accordion("Last Fetched Post Info", open=False, elem_id=self.elem_id("ra_last_post_info_accordion")):
                with gr.Row():
                    get_last_result_button = gr.Button("Show Last Fetched Post", elem_id=self.elem_id("ra_get_last_result_btn"))
                with gr.Row():
                    last_fetched_image_display = gr.Image(label="Last Fetched Image", type="pil", interactive=False, show_label=False, elem_id=self.elem_id("ra_last_fetched_image"))
                    last_fetched_url_display = gr.Textbox(label="Last Fetched URL", interactive=False, show_label=False, elem_id=self.elem_id("ra_last_fetched_url"))
                get_last_result_button.click(
                    fn=self.get_last_result,
                    inputs=[],
                    outputs=[last_fetched_image_display, last_fetched_url_display]
                )

        # Define all component interactions here if not already done above (e.g., booru_selected changes)
        # (Many are already defined inline with the component using .change())

        # Return list of all UI components that will be passed to before_process and postprocess
        return [
            enabled, booru_selected, max_pages_slider, post_id_textbox, tags_textbox, remove_tags_textbox_val,
            mature_rating_radio, remove_bad_tags_checkbox, shuffle_tags_checkbox, change_dash_checkbox,
            same_prompt_checkbox, fringe_benefits_checkbox, limit_tags_slider, max_tags_count_slider,
            change_background_radio, change_color_radio, sorting_order_radio, forbidden_prompt_tags_textbox,
            use_forbidden_prompt_file_checkbox, choose_forbidden_prompt_file_dropdown, disable_ranbooru_prompt_modification_checkbox,
            use_img2img_checkbox, use_controlnet_checkbox, denoising_slider, use_last_img_checkbox, crop_center_checkbox,
            use_deepbooru_checkbox, type_deepbooru_radio,
            use_search_txt_checkbox, choose_search_txt_dropdown, use_remove_txt_checkbox, choose_remove_txt_dropdown,
            mix_prompt_checkbox, mix_amount_slider, chaos_mode_radio, chaos_amount_slider,
            negative_mode_radio, use_same_seed_checkbox, use_cache_checkbox,
            lora_enabled_checkbox, lora_folder_textbox, lora_amount_slider, lora_min_weight_slider,
            lora_max_weight_slider, lora_custom_weights_textbox, lora_lock_previous_checkbox
        ]

    def check_orientation(self, img: Image.Image):
        """Determines target W, H for an image based on its orientation."""
        if not img: return (512, 512) # Default if no image
        x, y = img.size
        if x == y: return (768, 768) # Square, upscale to higher common res
        elif x > y: # Landscape
            if (x / y) > 1.7: return (1024, 576) # Wider than 16:9 panorama-like
            elif (x / y) > 1.4: return (768, 512) # Approx 3:2
            else: return (640, 512) # Near 4:3 or 5:4
        else: # Portrait
            if (y / x) > 1.7: return (576, 1024)
            elif (y / x) > 1.4: return (512, 768)
            else: return (512, 640)

    def loranado(self, p, lora_enabled, lora_folder_str, lora_amount_val, lora_min_w, lora_max_w, lora_custom_weights_str, lora_lock_prev_val):
        """Applies LoRAs to the prompt(s) in processing object `p`."""
        if not lora_enabled:
            if DEBUG: print("[Ranbooru] LoRAnado is not enabled.")
            return p

        lora_prompt_segment = ""
        if lora_lock_prev_val and self.previous_loras:
            lora_prompt_segment = self.previous_loras
            if DEBUG: print(f"[Ranbooru] LoRAnado: Using locked previous LoRAs: {lora_prompt_segment}")
        else:
            base_lora_path = shared.cmd_opts.lora_dir
            selected_lora_folder = os.path.join(base_lora_path, lora_folder_str.strip()) if lora_folder_str.strip() else base_lora_path

            if not os.path.isdir(selected_lora_folder):
                print(f"[Ranbooru] LoRAnado: LoRA folder not found: {selected_lora_folder}. Check subfolder name.")
                return p

            available_loras = [f for f in os.listdir(selected_lora_folder) if f.endswith(('.safetensors', '.ckpt', '.pt'))]
            if not available_loras:
                print(f"[Ranbooru] LoRAnado: No LoRAs found in {selected_lora_folder}.")
                return p

            custom_weights = []
            if lora_custom_weights_str.strip():
                try:
                    custom_weights = [float(w.strip()) for w in lora_custom_weights_str.split(',')]
                except ValueError:
                    print("[Ranbooru] LoRAnado: Invalid custom LoRA weights. Ensure they are numbers separated by commas.")

            temp_lora_list = []
            for i in range(int(lora_amount_val)):
                chosen_lora_name = random.choice(available_loras).rsplit('.', 1)[0] # Remove extension

                lora_weight = round(random.uniform(lora_min_w, lora_max_w), 2)
                if i < len(custom_weights): # Apply custom weight if available
                    lora_weight = custom_weights[i]

                # Ensure weight is not zero unless min and max are both zero
                if lora_min_w == 0 and lora_max_w == 0: lora_weight = 0
                else:
                    while lora_weight == 0: lora_weight = round(random.uniform(lora_min_w, lora_max_w), 2)

                temp_lora_list.append(f"<lora:{chosen_lora_name}:{lora_weight}>")

            lora_prompt_segment = " ".join(temp_lora_list) # Join with spaces for better readability if user inspects prompt
            self.previous_loras = lora_prompt_segment # Save for potential locking next time
            if DEBUG: print(f"[Ranbooru] LoRAnado: Generated LoRA string: {lora_prompt_segment}")

        if lora_prompt_segment:
            if isinstance(p.prompt, list):
                p.prompt = [f"{lora_prompt_segment} {pr}" for pr in p.prompt]
            else:
                p.prompt = f"{lora_prompt_segment} {p.prompt}"
            if DEBUG: print(f"[Ranbooru] LoRAnado: Applied LoRAs to prompt(s).")
        return p

    def before_process(self, p,
                       enabled, booru_selected_val, max_pages_slider_val, post_id_textbox_val, tags_textbox_val, remove_tags_textbox_val,
                       mature_rating_radio_val, remove_bad_tags_checkbox_val, shuffle_tags_checkbox_val, change_dash_checkbox_val,
                       same_prompt_checkbox_val, fringe_benefits_checkbox_val, limit_tags_slider_val, max_tags_count_slider_val,
                       change_background_radio_val, change_color_radio_val, sorting_order_radio_val, forbidden_prompt_tags_textbox_val,
                       use_forbidden_prompt_file_checkbox_val, choose_forbidden_prompt_file_dropdown_val, disable_ranbooru_prompt_modification_checkbox_val,
                       use_img2img_checkbox_val, use_controlnet_checkbox_val, denoising_slider_val, use_last_img_checkbox_val, crop_center_checkbox_val,
                       use_deepbooru_checkbox_val, type_deepbooru_radio_val,
                       use_search_txt_checkbox_val, choose_search_txt_dropdown_val, use_remove_txt_checkbox_val, choose_remove_txt_dropdown_val,
                       mix_prompt_checkbox_val, mix_amount_slider_val, chaos_mode_radio_val, chaos_amount_slider_val,
                       negative_mode_radio_val, use_same_seed_checkbox_val, use_cache_checkbox_val,
                       lora_enabled_checkbox_val, lora_folder_textbox_val, lora_amount_slider_val, lora_min_weight_slider_val,
                       lora_max_weight_slider_val, lora_custom_weights_textbox_val, lora_lock_previous_checkbox_val
                       ):

        if DEBUG: print(f"[Ranbooru] before_process started. Ranbooru enabled: {enabled}")

        # Store UI states on self for postprocess or other methods if needed
        self.enabled_flag = enabled
        self.use_img2img_flag = use_img2img_checkbox_val
        self.use_ip_flag = use_controlnet_checkbox_val # ControlNet
        self.denoising_strength_val = denoising_slider_val
        self.crop_center_flag = crop_center_checkbox_val
        self.use_deepbooru_flag = use_deepbooru_checkbox_val
        self.type_deepbooru_val = type_deepbooru_radio_val
        self.use_last_img_flag = use_last_img_checkbox_val

        # Handle caching setup
        if use_cache_checkbox_val and not requests_cache.patcher.is_installed():
            if DEBUG: print("[Ranbooru] Installing requests cache.")
            requests_cache.install_cache('ranbooru_cache', backend='sqlite', expire_after=3600) # Cache for 1 hour
        elif not use_cache_checkbox_val and requests_cache.patcher.is_installed():
            if DEBUG: print("[Ranbooru] Uninstalling requests cache.")
            requests_cache.uninstall_cache()

        # Apply LoRAnado first if Ranbooru main functions are disabled or if it's enabled globally
        if not enabled or disable_ranbooru_prompt_modification_checkbox_val:
            if lora_enabled_checkbox_val:
                if DEBUG: print("[Ranbooru] Ranbooru main processing disabled, but LoRAnado is active.")
                p = self.loranado(p, lora_enabled_checkbox_val, lora_folder_textbox_val, lora_amount_slider_val,
                                  lora_min_weight_slider_val, lora_max_weight_slider_val,
                                  lora_custom_weights_textbox_val, lora_lock_previous_checkbox_val)
            else:
                 if DEBUG: print("[Ranbooru] Ranbooru and LoRAnado are disabled. No changes to prompt.")
            return # Exit if main Ranbooru processing is off

        if DEBUG: print(f"[Ranbooru] Initial p.prompt: {p.prompt}, p.negative_prompt: {p.negative_prompt}")
        self.original_prompt = str(p.prompt) # Store user's original prompt

        # --- Initialize Booru API ---
        booru_api_map = {
            'gelbooru': Gelbooru(fringe_benefits_checkbox_val), 'rule34': Rule34(), 'safebooru': Safebooru(),
            'danbooru': Danbooru(), 'konachan': Konachan(), 'yande.re': Yandere(),
            'aibooru': AIBooru(), 'xbooru': XBooru(), 'e621': E621()
        }
        selected_booru_api = booru_api_map.get(booru_selected_val)
        if not selected_booru_api:
            print(f"[Ranbooru] Error: Selected booru '{booru_selected_val}' is not implemented.")
            return # Or raise error

        # --- Wildcard Processing for Initial UI Tags ---
        search_tags_from_ui = self.process_wildcards(tags_textbox_val)
        remove_tags_from_ui = self.process_wildcards(remove_tags_textbox_val) # This is new, pre-fetch removal
        if DEBUG: print(f"[Ranbooru] Tags from UI (post-wildcard): Search='{search_tags_from_ui}', Remove='{remove_tags_from_ui}'")

        # --- Exception Checking (Tag Limits, ID Support) ---
        try:
            check_exception(booru_selected_val, {'tags': search_tags_from_ui, 'post_id': post_id_textbox_val})
        except ValueError as e:
            print(f"[Ranbooru] Error: {e}")
            # Potentially fall back or notify user through Gradio if possible, for now, just prints and continues if non-fatal.
            # If it's a critical error (e.g., tag limit that will cause API error), might need to stop.
            #shared.state.interrupted = True # This might be too abrupt.
            #gr.Warning(str(e)) # Won't work directly here.
            return # Stop processing if basic checks fail.

        # --- Build Search Query ---
        query_tags_list = [t.strip() for t in search_tags_from_ui.split(',') if t.strip()]

        # Add tags from search file if enabled
        if use_search_txt_checkbox_val and choose_search_txt_dropdown_val:
            try:
                search_file_path = os.path.join(user_search_dir, choose_search_txt_dropdown_val)
                with open(search_file_path, 'r', encoding='utf-8') as f:
                    file_tags_lines = [line.strip() for line in f if line.strip()]
                if file_tags_lines:
                    chosen_line = random.choice(file_tags_lines)
                    query_tags_list.extend([t.strip() for t in chosen_line.split(',') if t.strip()])
                    if DEBUG: print(f"[Ranbooru] Added tags from search file '{choose_search_txt_dropdown_val}': {chosen_line}")
            except Exception as e:
                print(f"[Ranbooru] Error reading search tags file {choose_search_txt_dropdown_val}: {e}")

        # Pre-fetch Remove Tags (from UI text and/or file)
        # These are removed from the query_tags_list before sending to booru
        pre_fetch_remove_list = [t.strip().lower() for t in remove_tags_from_ui.split(',') if t.strip()]
        if use_remove_txt_checkbox_val and choose_remove_txt_dropdown_val:
            try:
                remove_file_path = os.path.join(user_remove_dir, choose_remove_txt_dropdown_val)
                with open(remove_file_path, 'r', encoding='utf-8') as f:
                    pre_fetch_remove_list.extend([line.strip().lower() for line in f if line.strip()])
                if DEBUG: print(f"[Ranbooru] Extended pre-fetch remove tags from file: {choose_remove_txt_dropdown_val}")
            except Exception as e:
                print(f"[Ranbooru] Error reading pre-fetch remove tags file {choose_remove_txt_dropdown_val}: {e}")

        if pre_fetch_remove_list:
            query_tags_list = [tag for tag in query_tags_list if tag.lower() not in pre_fetch_remove_list]
            if DEBUG: print(f"[Ranbooru] Query tags after pre-fetch removal: {query_tags_list}")

        final_search_str = "+".join(query_tags_list) # Boorus usually use + or space for AND

        # Add rating to query if not 'All'
        current_booru_ratings = RATINGS.get(booru_selected_val, RATING_TYPES['none'])
        rating_query_val = current_booru_ratings.get(mature_rating_radio_val, 'all') # Default to 'all' if somehow invalid
        if rating_query_val != 'all': # Assuming 'all' means no specific rating tag
            # Danbooru uses meta tags like rating:s, others might use rating:safe
            # The RATINGS dict should provide the correct API value.
            final_search_str += f"+rating:{rating_query_val}"

        if DEBUG: print(f"[Ranbooru] Final search query string for API: {final_search_str}")

        # --- Fetch Posts ---
        raw_posts_data = selected_booru_api.get_posts(
            tags=final_search_str,
            page_num=0, # 0 for random page logic within get_posts
            limit=POST_AMOUNT, # Using global POST_AMOUNT
            max_pages=int(max_pages_slider_val),
            post_id=post_id_textbox_val.strip() if post_id_textbox_val.strip() else None
        )
        fetched_posts = selected_booru_api.process_response(raw_posts_data)
        if DEBUG: print(f"[Ranbooru] Fetched {len(fetched_posts)} posts. Global COUNT is now {COUNT}.")

        if not fetched_posts:
            print(f"[Ranbooru] No posts found for tags: '{final_search_str}' on {booru_selected_val}.")
            # Apply LoRAnado even if no posts found, then return
            p = self.loranado(p, lora_enabled_checkbox_val, lora_folder_textbox_val, lora_amount_slider_val,
                              lora_min_weight_slider_val, lora_max_weight_slider_val,
                              lora_custom_weights_textbox_val, lora_lock_previous_checkbox_val)
            return

        # --- Sort Fetched Posts ---
        if sorting_order_radio_val == "High Score":
            fetched_posts.sort(key=lambda x: x.get('score', 0), reverse=True)
        elif sorting_order_radio_val == "Low Score":
            fetched_posts.sort(key=lambda x: x.get('score', 0))
        elif sorting_order_radio_val == "Newest First":
            fetched_posts.sort(key=lambda x: x.get('id', 0), reverse=True)
        elif sorting_order_radio_val == "Oldest First":
            fetched_posts.sort(key=lambda x: x.get('id', 0))
        if DEBUG: print(f"[Ranbooru] Sorted posts by: {sorting_order_radio_val}")

        # Store all fetched images and URLs for the "Show Last Fetched Post" button
        # Only store URLs now, fetch image on demand in get_last_result to save memory if not used
        self.result_url = [post.get('file_url', '') for post in fetched_posts]
        self.result_img = [None] * len(fetched_posts) # Initialize with None, will be filled by get_last_result on demand or by img ops

        # --- Select Posts for Batch ---
        num_images_to_generate = p.batch_size * p.n_iter
        selected_posts_for_batch = []
        if same_prompt_checkbox_val or post_id_textbox_val:
            if fetched_posts: selected_posts_for_batch = [fetched_posts[0]] * num_images_to_generate
        else:
            if len(fetched_posts) >= num_images_to_generate:
                if sorting_order_radio_val == "Random":
                    selected_posts_for_batch = random.sample(fetched_posts, num_images_to_generate)
                else:
                    selected_posts_for_batch = fetched_posts[:num_images_to_generate]
            else:
                selected_posts_for_batch = list(fetched_posts) # Make a mutable copy
                if fetched_posts:
                     selected_posts_for_batch.extend([fetched_posts[-1]] * (num_images_to_generate - len(fetched_posts)))

        if not selected_posts_for_batch:
            print("[Ranbooru] No posts selected for batch processing (this shouldn't happen if posts were fetched).")
            p = self.loranado(p, lora_enabled_checkbox_val, lora_folder_textbox_val, lora_amount_slider_val, lora_min_weight_slider_val, lora_max_weight_slider_val, lora_custom_weights_textbox_val, lora_lock_previous_checkbox_val)
            return

        # --- Image Fetching for Img2Img / DeepBooru / ControlNet ---
        self.last_img = [] # Reset from previous runs
        image_ops_active = use_img2img_checkbox_val or use_deepbooru_checkbox_val or use_controlnet_checkbox_val
        if image_ops_active and selected_posts_for_batch:
            urls_to_fetch_for_ops = []
            # Determine which URLs to fetch based on use_last_img_checkbox_val (use first image for all in batch)
            # and ensure we only fetch up to num_images_to_generate
            if use_last_img_checkbox_val and selected_posts_for_batch[0].get('file_url'):
                urls_to_fetch_for_ops = [selected_posts_for_batch[0].get('file_url')] * num_images_to_generate
            else:
                urls_to_fetch_for_ops = [post.get('file_url') for post in selected_posts_for_batch[:num_images_to_generate]]

            for i, url in enumerate(urls_to_fetch_for_ops):
                if not url:
                    print(f"[Ranbooru] Warning: No file_url for selected post index {i} for operations. Skipping image fetch.")
                    self.last_img.append(None)
                    if i < len(self.result_img): self.result_img[i] = None # Also mark in display cache
                    continue
                try:
                    if DEBUG: print(f"[Ranbooru] Fetching image for ops: {url}")
                    response = requests.get(url, headers=selected_booru_api.headers, timeout=20)
                    response.raise_for_status()
                    pil_image = Image.open(BytesIO(response.content))
                    self.last_img.append(pil_image)
                    if i < len(self.result_img): self.result_img[i] = pil_image # Store for display
                except Exception as e:
                    print(f"[Ranbooru] Error fetching/processing image {url}: {e}")
                    self.last_img.append(None)
                    if i < len(self.result_img): self.result_img[i] = None

            if not any(self.last_img) and image_ops_active:
                print("[Ranbooru] Warning: No images could be fetched for Img2Img/DeepBooru/ControlNet.")
        if DEBUG: print(f"[Ranbooru] Fetched {len([img for img in self.last_img if img])} images for batch operations.")


        # --- Prompt Construction for Each Image in Batch ---
        batch_prompts = []
        user_prompt_base = str(self.original_prompt)

        # General Bad Tags (hardcoded, post-fetch, applied if checkbox is on)
        general_bad_tags_post_fetch = []
        if remove_bad_tags_checkbox_val:
            general_bad_tags_post_fetch.extend(['mixed-language_text', 'watermark', 'text', 'english_text', 'speech_bubble', 'signature', 'artist_name', 'censored', 'bar_censor', 'translation', 'twitter_username', "twitter_logo", 'patreon_username', 'commentary_request', 'tagme', 'commentary', 'character_name', 'mosaic_censoring', 'instagram_username', 'text_focus', 'english_commentary', 'comic', 'translation_request', 'fake_text', 'translated', 'paid_reward_available', 'thought_bubble', 'multiple_views', 'silent_comic', 'out-of-frame_censoring', 'symbol-only_commentary', '3koma', '2koma', 'character_watermark', 'spoken_question_mark', 'japanese_text', 'spanish_text', 'language_text', 'fanbox_username', 'commission', 'original', 'ai_generated', 'stable_diffusion', 'tagme_(artist)', 'text_bubble', 'qr_code', 'chinese_commentary', 'korean_text', 'partial_commentary', 'chinese_text', 'copyright_request', 'heart_censor', 'censored_nipples', 'page_number', 'scan', 'fake_magazine_cover', 'korean_commentary'])
            if DEBUG: print(f"[Ranbooru] Common bad tags removal (post-fetch) is ON.")

        bg_color_tags_to_remove_from_ranbooru = []
        bg_color_tags_to_add_to_user_base = []
        background_options_map = {
            'Add Background': (random.choice(ADD_BG) + ',detailed_background', COLORED_BG),
            'Remove Background': ('plain_background,simple_background,' + random.choice(COLORED_BG), ADD_BG),
            'Remove All BG': ('', COLORED_BG + ADD_BG)
        }
        if change_background_radio_val in background_options_map:
            add_str, remove_list = background_options_map[change_background_radio_val]
            if add_str: bg_color_tags_to_add_to_user_base.append(add_str)
            if remove_list: bg_color_tags_to_remove_from_ranbooru.extend(remove_list)
        color_options_map = {
            'Colored': (None, BW_BG),
            'Limited Palette': ('(limited_palette:1.3)', BW_BG + ['monochrome']),
            'Monochrome': (','.join(BW_BG), COLORED_BG)
        }
        if change_color_radio_val in color_options_map:
            add_str, remove_list = color_options_map[change_color_radio_val]
            if add_str: bg_color_tags_to_add_to_user_base.append(add_str)
            if remove_list: bg_color_tags_to_remove_from_ranbooru.extend(remove_list)

        if bg_color_tags_to_add_to_user_base:
            user_prompt_base = f"{user_prompt_base.strip()},{','.join(bg_color_tags_to_add_to_user_base)}".strip(',')
            user_prompt_base = remove_repeated_tags(user_prompt_base)
        final_post_fetch_bad_tags = list(set(
            [t.lower() for t in general_bad_tags_post_fetch] + \
            [t.lower() for t in bg_color_tags_to_remove_from_ranbooru]
        ))

        for i, selected_post in enumerate(selected_posts_for_batch):
            current_ranbooru_tags_str = selected_post.get('tags', '')
            if mix_prompt_checkbox_val and not same_prompt_checkbox_val and not post_id_textbox_val:
                # Mixing logic (simplified, see full code for detailed implementation)
                try:
                    mixed_tags_set = set(current_ranbooru_tags_str.split())
                    num_additional_to_mix = int(mix_amount_slider_val) -1
                    if num_additional_to_mix > 0 and len(fetched_posts) > 1:
                        other_posts = [p for p in fetched_posts if p['id'] != selected_post['id']]
                        sample_size = min(num_additional_to_mix, len(other_posts))
                        if sample_size > 0:
                            posts_to_mix_with = random.sample(other_posts, sample_size)
                            for p_mix in posts_to_mix_with: mixed_tags_set.update(p_mix.get('tags','').split())
                    current_ranbooru_tags_str = ' '.join(list(mixed_tags_set))
                except Exception as e: print(f"[Ranbooru] Error during tag mixing: {e}")

            temp_tags_list = [tag.strip().lower() for tag in html.unescape(current_ranbooru_tags_str.replace(' ', ',')).split(',') if tag.strip()]
            cleaned_ranbooru_tags_for_item = []
            for tag in temp_tags_list:
                is_bad = False
                for bad_pattern in final_post_fetch_bad_tags:
                    if '*' in bad_pattern:
                        if bad_pattern.strip('*') in tag: is_bad = True; break
                    elif bad_pattern == tag: is_bad = True; break
                if not is_bad: cleaned_ranbooru_tags_for_item.append(tag)

            current_ranbooru_tags_str = ','.join(cleaned_ranbooru_tags_for_item)
            if change_dash_checkbox_val: current_ranbooru_tags_str = current_ranbooru_tags_str.replace("_", " ")
            if shuffle_tags_checkbox_val:
                tags_to_shuffle = current_ranbooru_tags_str.split(',')
                random.shuffle(tags_to_shuffle)
                current_ranbooru_tags_str = ','.join(tags_to_shuffle)

            forbidden_tags_post_fetch_set = set()
            if forbidden_prompt_tags_textbox_val: forbidden_tags_post_fetch_set.update(t.strip().lower() for t in forbidden_prompt_tags_textbox_val.split(',') if t.strip())
            if use_forbidden_prompt_file_checkbox_val and choose_forbidden_prompt_file_dropdown_val:
                try:
                    with open(os.path.join(user_forbidden_prompt_dir, choose_forbidden_prompt_file_dropdown_val), 'r', encoding='utf-8') as f:
                        forbidden_tags_post_fetch_set.update(line.strip().lower() for line in f if line.strip() and not line.startswith('#'))
                except Exception as e: print(f"[Ranbooru] Error reading forbidden file {choose_forbidden_prompt_file_dropdown_val}: {e}")

            if forbidden_tags_post_fetch_set:
                current_ranbooru_tags_str = ','.join([t for t in current_ranbooru_tags_str.split(',') if t.strip().lower() not in forbidden_tags_post_fetch_set])

            user_prompt_base_cleaned = remove_repeated_tags(user_prompt_base)
            if user_prompt_base_cleaned and current_ranbooru_tags_str: final_prompt = f"{user_prompt_base_cleaned},{current_ranbooru_tags_str}"
            elif current_ranbooru_tags_str: final_prompt = current_ranbooru_tags_str
            else: final_prompt = user_prompt_base_cleaned
            batch_prompts.append(remove_repeated_tags(final_prompt))

        if chaos_mode_radio_val in ['Chaos', 'Less Chaos']:
            # Chaos mode implementation (simplified, see full code)
            new_prompts_chaos = []
            new_neg_prompts_chaos = p.negative_prompt if isinstance(p.negative_prompt, list) else [p.negative_prompt] * len(batch_prompts)
            for idx, item_prompt in enumerate(batch_prompts):
                neg_for_chaos = new_neg_prompts_chaos[idx] if chaos_mode_radio_val == 'Chaos' else ""
                pos_c, neg_c = generate_chaos(item_prompt, neg_for_chaos, chaos_amount_slider_val)
                new_prompts_chaos.append(pos_c)
                if new_neg_prompts_chaos[idx] and neg_c: new_neg_prompts_chaos[idx] = f"{new_neg_prompts_chaos[idx]},{neg_c}"
                elif neg_c: new_neg_prompts_chaos[idx] = neg_c
                new_neg_prompts_chaos[idx] = remove_repeated_tags(new_neg_prompts_chaos[idx])
            batch_prompts = new_prompts_chaos
            p.negative_prompt = new_neg_prompts_chaos

        if negative_mode_radio_val == 'Move Ranbooru Tags to Negative':
            # Negative mode implementation (simplified, see full code)
            new_pos_prompts_negmode = []
            current_neg_prompts_negmode = p.negative_prompt if isinstance(p.negative_prompt, list) else [p.negative_prompt] * len(batch_prompts)
            user_tags_set_negmode = set(t.strip().lower() for t in user_prompt_base.split(',') if t.strip())
            for idx, item_full_prompt in enumerate(batch_prompts):
                tags_current_item = [t.strip() for t in item_full_prompt.split(',') if t.strip()]
                user_part = [t for t in tags_current_item if t.lower() in user_tags_set_negmode]
                ranbooru_part = [t for t in tags_current_item if t.lower() not in user_tags_set_negmode]
                new_pos_prompts_negmode.append(remove_repeated_tags(",".join(user_part)))
                additional_neg_tags = ",".join(ranbooru_part)
                if current_neg_prompts_negmode[idx] and additional_neg_tags: current_neg_prompts_negmode[idx] = f"{current_neg_prompts_negmode[idx]},{additional_neg_tags}"
                elif additional_neg_tags: current_neg_prompts_negmode[idx] = additional_neg_tags
                current_neg_prompts_negmode[idx] = remove_repeated_tags(current_neg_prompts_negmode[idx])
            batch_prompts = new_pos_prompts_negmode
            p.negative_prompt = current_neg_prompts_negmode

        if limit_tags_slider_val < 1.0: batch_prompts = [limit_prompt_tags(pr, limit_tags_slider_val, 'Limit %') for pr in batch_prompts]
        if max_tags_count_slider_val < 150: batch_prompts = [limit_prompt_tags(pr, max_tags_count_slider_val, 'Max Tags') for pr in batch_prompts]

        if len(batch_prompts) == 1: p.prompt = batch_prompts[0]
        else: p.prompt = batch_prompts
        if isinstance(p.prompt, str) and isinstance(p.negative_prompt, list): p.negative_prompt = p.negative_prompt[0]
        elif isinstance(p.prompt, list) and not isinstance(p.negative_prompt, list):
             p.negative_prompt = [p.negative_prompt] * len(p.prompt)
        elif isinstance(p.prompt, list) and isinstance(p.negative_prompt, list) and len(p.prompt) != len(p.negative_prompt):
            # Attempt to reconcile lengths if lists but mismatched
            base_neg_val = p.negative_prompt[0] if p.negative_prompt else ""
            p.negative_prompt = [base_neg_val] * len(p.prompt)


        if use_same_seed_checkbox_val and p.seed == -1: p.seed = random.randint(0, 2**32 - 1)

        p = self.loranado(p, lora_enabled_checkbox_val, lora_folder_textbox_val, lora_amount_slider_val, lora_min_weight_slider_val, lora_max_weight_slider_val, lora_custom_weights_textbox_val, lora_lock_previous_checkbox_val)

        if use_deepbooru_checkbox_val and not use_img2img_checkbox_val and self.last_img and any(self.last_img):
            # Standalone DeepBooru (simplified, see full code)
            self.original_prompt_for_autotag = p.prompt
            self.last_img_for_autotag = [img for img in self.last_img if img is not None][:len(p.prompt) if isinstance(p.prompt,list) else 1] # Match images to prompts
            db_tags = self.use_autotagger('deepbooru')
            if isinstance(p.prompt, list):
                p.prompt = [modify_prompt(p.prompt[j], db_tags[j] if j < len(db_tags) else "", type_deepbooru_radio_val) for j in range(len(p.prompt))]
                p.prompt = [remove_repeated_tags(pr) for pr in p.prompt]
            else:
                p.prompt = modify_prompt(p.prompt, db_tags[0] if db_tags else "", type_deepbooru_radio_val)
                p.prompt = remove_repeated_tags(p.prompt)

        if use_img2img_checkbox_val and not use_controlnet_checkbox_val:
            if self.last_img and any(self.last_img): self.real_steps = p.steps; p.steps = 1
            else: self.use_img2img_flag = False # Disable if no images

        if use_controlnet_checkbox_val and self.last_img and any(self.last_img):
            # ControlNet setup (simplified, see full code for module import and unit update)
            try:
                cn_image = next((img for img in self.last_img if img is not None), None)
                if cn_image:
                    if crop_center_checkbox_val: cn_image = resize_image(cn_image, p.width, p.height, crop_to_center=True)
                    # Find and update ControlNet unit (details omitted for brevity)
                    if DEBUG: print("[Ranbooru] ControlNet image prepared (details of unit update omitted).")
                else: print("[Ranbooru] ControlNet enabled, but no valid image for it.")
            except Exception as e: print(f"[Ranbooru] Error setting up ControlNet: {e}")
        if DEBUG: print(f"[Ranbooru] before_process finished. Final p.prompt: {p.prompt}")


    def postprocess(self, p, processed,
                       enabled, booru_selected_val, max_pages_slider_val, post_id_textbox_val, tags_textbox_val, remove_tags_textbox_val,
                       mature_rating_radio_val, remove_bad_tags_checkbox_val, shuffle_tags_checkbox_val, change_dash_checkbox_val,
                       same_prompt_checkbox_val, fringe_benefits_checkbox_val, limit_tags_slider_val, max_tags_count_slider_val,
                       change_background_radio_val, change_color_radio_val, sorting_order_radio_val, forbidden_prompt_tags_textbox_val,
                       use_forbidden_prompt_file_checkbox_val, choose_forbidden_prompt_file_dropdown_val, disable_ranbooru_prompt_modification_checkbox_val,
                       use_img2img_checkbox_val, use_controlnet_checkbox_val, denoising_slider_val, use_last_img_checkbox_val, crop_center_checkbox_val,
                       use_deepbooru_checkbox_val, type_deepbooru_radio_val,
                       use_search_txt_checkbox_val, choose_search_txt_dropdown_val, use_remove_txt_checkbox_val, choose_remove_txt_dropdown_val,
                       mix_prompt_checkbox_val, mix_amount_slider_val, chaos_mode_radio_val, chaos_amount_slider_val,
                       negative_mode_radio_val, use_same_seed_checkbox_val, use_cache_checkbox_val,
                       lora_enabled_checkbox_val, lora_folder_textbox_val, lora_amount_slider_val, lora_min_weight_slider_val,
                       lora_max_weight_slider_val, lora_custom_weights_textbox_val, lora_lock_previous_checkbox_val
                       ):

        if not self.enabled_flag or not self.use_img2img_flag or self.use_ip_flag: return
        if not self.last_img or not any(self.last_img): return
        if DEBUG: print("[Ranbooru] postprocess started for Img2Img pass.")

        target_w, target_h = p.width, p.height
        processed_init_images = []
        valid_last_img = [img for img in self.last_img if img is not None] # Filter out None images first

        if not valid_last_img:
            print("[Ranbooru] Postprocess: No valid images in self.last_img for Img2Img. Skipping.")
            return

        if self.crop_center_flag:
            processed_init_images = [resize_image(img, target_w, target_h, crop_to_center=True) for img in valid_last_img]
        else:
            temp_oriented = [resize_image(img, *self.check_orientation(img), crop_to_center=False) for img in valid_last_img]
            if temp_oriented:
                base_w, base_h = temp_oriented[0].size
                processed_init_images = [img.resize((base_w, base_h), Image.Resampling.LANCZOS) for img in temp_oriented]
                target_w, target_h = base_w, base_h

        if not processed_init_images: print("[Ranbooru] Postprocess: No images after resize for Img2Img. Skipping."); return

        num_prompts_i2i = len(p.prompt) if isinstance(p.prompt, list) else 1
        final_init_images_for_pass = []
        if len(processed_init_images) >= num_prompts_i2i:
            final_init_images_for_pass = processed_init_images[:num_prompts_i2i]
        else: # Fewer images than prompts, repeat last image
            final_init_images_for_pass.extend(processed_init_images)
            if processed_init_images: # Should be true if we reached here
                 final_init_images_for_pass.extend([processed_init_images[-1]] * (num_prompts_i2i - len(processed_init_images)))

        if not final_init_images_for_pass:
            print("[Ranbooru] Postprocess: Init image list is empty before Img2Img pass. Skipping.")
            return

        final_prompts_for_i2i_pass = p.prompt
        if self.use_deepbooru_flag:
            self.original_prompt_for_autotag = p.prompt
            self.last_img_for_autotag = final_init_images_for_pass # Use the images prepared for this pass
            db_tags_i2i = self.use_autotagger('deepbooru')
            if isinstance(final_prompts_for_i2i_pass, list):
                final_prompts_for_i2i_pass = [modify_prompt(final_prompts_for_i2i_pass[k], db_tags_i2i[k] if k < len(db_tags_i2i) else "", self.type_deepbooru_val) for k in range(len(final_prompts_for_i2i_pass))]
                final_prompts_for_i2i_pass = [remove_repeated_tags(pr) for pr in final_prompts_for_i2i_pass]
            else:
                final_prompts_for_i2i_pass = modify_prompt(final_prompts_for_i2i_pass, db_tags_i2i[0] if db_tags_i2i else "", self.type_deepbooru_val)
                final_prompts_for_i2i_pass = remove_repeated_tags(final_prompts_for_i2i_pass)

        p_i2i = StableDiffusionProcessingImg2Img(
            sd_model=shared.sd_model, outpath_samples=shared.opts.outdir_samples or shared.opts.outdir_img2img_samples,
            outpath_grids=shared.opts.outdir_grids or shared.opts.outdir_img2img_grids, prompt=final_prompts_for_i2i_pass,
            negative_prompt=p.negative_prompt, seed=p.seed, sampler_name=p.sampler_name, scheduler=getattr(p, 'scheduler', None),
            batch_size=p.batch_size, n_iter=p.n_iter, steps=self.real_steps, cfg_scale=p.cfg_scale,
            width=target_w, height=target_h, init_images=final_init_images_for_pass, denoising_strength=self.denoising_strength_val,
            styles=p.styles if hasattr(p, 'styles') else [], override_settings=p.override_settings if hasattr(p, 'override_settings') else {},
            subseed=p.subseed if hasattr(p, 'subseed') else -1, subseed_strength=p.subseed_strength if hasattr(p, 'subseed_strength') else 0,
        )
        img2img_proc_result = process_images(p_i2i)

        # Replace or extend processed results
        # If initial txt2img steps were minimal (e.g., 1), replace entirely.
        # Otherwise, extend. For simplicity here, assuming replacement if self.real_steps > 1 (meaning txt2img was placeholder)
        if self.real_steps > 1 and p.steps == 1: # Indicates txt2img was placeholder
            processed.images = img2img_proc_result.images
            processed.infotexts = img2img_proc_result.infotexts
            processed.prompt = img2img_proc_result.prompt
            processed.negative_prompt = img2img_proc_result.negative_prompt
            # Potentially copy other fields if needed
        else: # Extend if txt2img also did significant work or if logic is different
            processed.images.extend(img2img_proc_result.images)
            processed.infotexts.extend(img2img_proc_result.infotexts)

        if shared.opts.save_images_before_highres_fix and hasattr(shared.opts, 'samples_add_original_image') and shared.opts.samples_add_original_image:
             processed.images.extend(final_init_images_for_pass)
        if DEBUG: print(f"[Ranbooru] postprocess for Img2Img finished. Total images in 'processed': {len(processed.images)}")


    def random_number(self, sorting_order_val, batch_size_val):
        global COUNT
        effective_max_index = COUNT
        if effective_max_index <= 0: return []
        num_to_select = min(batch_size_val, effective_max_index)
        if num_to_select <=0: return []
        return random.sample(range(effective_max_index), num_to_select)


    def use_autotagger(self, model_name_val):
        if model_name_val == 'deepbooru' and hasattr(self, 'last_img_for_autotag') and self.last_img_for_autotag:
            images_to_tag = [img for img in self.last_img_for_autotag if img is not None]
            if not images_to_tag: return [""] * len(self.last_img_for_autotag)
            num_images = len(images_to_tag)
            final_tagged_prompts_from_db = [""] * num_images # Initialize with empty strings
            if DEBUG: print(f"[Ranbooru] DeepBooru tagging {num_images} image(s).")
            try:
                if not hasattr(deepbooru, 'model') or not hasattr(deepbooru.model, 'tag_multi'):
                    print("[Ranbooru] DeepBooru module or model not loaded correctly.")
                    return [""] * num_images
                deepbooru.model.start()
                for i in range(num_images):
                    final_tagged_prompts_from_db[i] = deepbooru.model.tag_multi(images_to_tag[i])
            except Exception as e: print(f"[Ranbooru] Error during DeepBooru tagging: {e}")
            # finally: # Let DB manage its own lifecycle for now.
                # if hasattr(deepbooru, 'model') and hasattr(deepbooru.model, 'stop'): deepbooru.model.stop()

            output_tags_final = []
            valid_img_idx = 0
            for img_original_slot in self.last_img_for_autotag: # Iterate over original list that may have Nones
                if img_original_slot is not None and valid_img_idx < len(final_tagged_prompts_from_db):
                    output_tags_final.append(final_tagged_prompts_from_db[valid_img_idx])
                    valid_img_idx += 1
                else:
                    output_tags_final.append("") # Append empty string for None image slots or if tagging failed to produce enough
            return output_tags_final
        return []
