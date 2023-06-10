import os
import shutil
import sqlite3
import time
import logging
logging.getLogger('downloader').setLevel(logging.CRITICAL)

import moviepy.editor as mp
import nltk
import wikipedia
from PIL import Image
from bing_image_downloader import downloader
from gtts import gTTS
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from pytrends.request import TrendReq
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


def generate_chrome_options():
    username = os.getlogin()
    # Configure Chrome options
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument('--headless')  # Run Chrome in headless mode (without a visible browser window)
    chrome_options.add_argument('--no-sandbox')  # Bypass OS security model
    chrome_options.add_argument('--disable-dev-shm-usage')  # Disable "DevShmUsage" flag
    chrome_options.add_argument(fr'--user-data-dir=C:\\Users\\{username}\\AppData\\Local\\Google\\Chrome\\User Data')
    chrome_options.add_argument(
        fr'--profile-directory=C:\\Users\\{username}\\AppData\\Local\\Google\\Chrome\\User Data\\Default')
    return chrome_options


def create_workspace():
    workspace_path = os.path.join(os.getcwd(), "workspace", query)
    images_dir = os.path.join(workspace_path, "images")
    synced_images_dir = os.path.join(workspace_path, "synced")
    audio_dir = os.path.join(workspace_path, "audio")
    video_dir = os.path.join(workspace_path, "video", query)
    audio_path = os.path.join(audio_dir, "speak.mp3")
    video_path = os.path.join(video_dir, f"{query}.mp4")
    os.makedirs(workspace_path, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(synced_images_dir, exist_ok=True)
    os.makedirs(video_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)
    return workspace_path, audio_path, video_path, audio_dir, video_dir, synced_images_dir, images_dir


def get_wikipedia_summary(search_text, lists=1):
    try:
        data = wikipedia.page(title=search_text, auto_suggest=True)
        text = data.summary
        title = data.title
        return title, text

    except wikipedia.exceptions.DisambiguationError as e:
        if lists < len(e.options):
            option = e.options[lists]
            print(f"{e}\nSearch text replaced. {option} is the new search title.")
            return get_wikipedia_summary(option, lists + 1)
        else:
            print("No more options available.")
            return None, None

    except wikipedia.exceptions.PageError:
        print("Page error for Wikipedia search.")
        return None, None


def download_images():
    downloader.download(query, limit=images_count, output_dir=images_dir, adult_filter_off=True,
                        force_replace=False, timeout=1, verbose=False)

    source_dir = os.path.join(images_dir, query)
    destination_dir = images_dir

    # Get a list of all files in the source directory
    files = os.listdir(source_dir)

    # Iterate over each file and move it to the destination directory
    for file_name in files:
        source_path = os.path.join(source_dir, file_name)
        destination_path = os.path.join(destination_dir, file_name)
        shutil.move(source_path, destination_path)

    shutil.rmtree(source_dir)


def sync_images():
    downloaded_images_list = []

    for downloaded_image_name in os.listdir(images_dir):
        downloaded_images_list.append(os.path.join(images_dir, downloaded_image_name))

    # Find the smallest photo in the list
    smallest_size = None
    for file_path in downloaded_images_list:
        image = Image.open(file_path)
        if smallest_size is None or image.size[0] < smallest_size[0]:
            smallest_size = image.size

    for file_path in downloaded_images_list:
        # Open the image file
        image = Image.open(file_path)

        # Convert the image to RGB if not already in RGB format
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize the image to a 9:16 aspect ratio
        aspect_ratio = 9 / 16
        new_width = int(smallest_size[1] * aspect_ratio)
        image = image.resize((new_width, smallest_size[1]), resample=Image.LANCZOS)
        # Save the image to the synced folder as JPEG
        filename = os.path.basename(file_path)
        image.save(os.path.join(synced_images_dir, filename), "JPEG")
        os.remove(file_path)


def create_video():
    # Load images and calculate duration of each image
    images = os.listdir(synced_images_dir)
    per_image_duration = duration / len(images)
    clips = []
    # Create a video
    for i, image in enumerate(images):
        clip = mp.ImageClip(img=os.path.join(synced_images_dir, image), duration=per_image_duration)
        clip.fps = 24
        clips.append(clip)

    video = mp.concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio)

    # Save the video
    video.write_videofile(video_path, fps=24, codec="mpeg4")


def generate_keywords(text):
    # Tokenize the text into individual words
    tokens = word_tokenize(text)

    # Remove stopwords (common words that don't carry much meaning)
    stop_words = set(stopwords.words('english'))
    filtered_tokens = [word for word in tokens if word.lower() not in stop_words]

    # Perform part-of-speech tagging
    tagged_tokens = nltk.pos_tag(filtered_tokens)

    # Extract nouns and adjectives as keywords
    keywords = [word for word, pos in tagged_tokens if pos.startswith('N') or pos.startswith('J')]
    return keywords


def short_keywords(keyword_list):
    """
    This function takes a list of keywords and returns a shorter list of keywords,
    up to a maximum of 500 characters. The keywords are separated by commas.

    Args:
      keyword_list: A list of strings.

    Returns:
      A string of keywords, separated by commas.
    """
    # Generate a string from list with commas separating the keywords.
    keyword_string = ','.join(keyword_list)
    # Get the length of the keyword string.
    length = len(keyword_string)

    # If the keyword string is less than or equal to 500 characters, return it as a string.
    if length <= 500:
        return keyword_string
    else:
        new_list = []
        total_length = 0

        # Iterate through the keyword_list and add keywords to new_list until the total length exceeds 500 characters.
        for keyword in keyword_list:
            # Check if adding the current keyword exceeds the maximum length of 500 characters.
            if total_length + len(keyword) + len(new_list) <= 500:
                new_list.append(keyword)
                total_length += len(keyword)
            else:
                break

        # Return the new list of keywords as a string, separated by commas.
        return ','.join(new_list)


def upload_video_youtube(file_path, description: str, title: str, keywords: str):
    try:
        wait = WebDriverWait(driver, 10)

        create_icon = wait.until(ec.element_to_be_clickable((By.CSS_SELECTOR, '#create-icon > div')))
        create_icon.click()
        time.sleep(1)

        text_item = wait.until(ec.element_to_be_clickable((By.CSS_SELECTOR, '#text-item-0 yt-formatted-string')))
        text_item.click()
        time.sleep(1)

        file_input = driver.find_element(By.XPATH, "//input[@type='file']")
        file_input.send_keys(file_path)
        time.sleep(1)

        # Wait for the details section to be visible
        wait.until(ec.visibility_of_element_located((By.ID, 'reuse-details-button')))
        time.sleep(1)

        # Fill in the video title
        title_input = driver.find_element(By.XPATH,
                                          '/html/body/ytcp-uploads-dialog/tp-yt-paper-dialog/div/ytcp-animatable[1]/ytcp-ve/ytcp-video-metadata-editor/div/ytcp-video-metadata-editor-basics/div[1]/ytcp-social-suggestions-textbox/ytcp-form-input-container/div[1]/div[2]/div/ytcp-social-suggestion-input/div')
        time.sleep(0.5)
        title_input.clear()
        time.sleep(0.5)
        title_input.send_keys(title)
        time.sleep(1)

        # Fill in the video description
        description_input = wait.until(
            ec.element_to_be_clickable((By.CSS_SELECTOR, 'div.description ytcp-social-suggestion-input > div')))
        description_input.send_keys(description)
        time.sleep(1)

        # Set the video as not made for kids
        not_made_for_kids_radio = wait.until(ec.element_to_be_clickable(
            (By.CSS_SELECTOR, 'ytkc-made-for-kids-select tp-yt-paper-radio-button:nth-of-type(2) ytcp-ve')))
        not_made_for_kids_radio.click()
        time.sleep(1)

        # Enable comments on the video
        toggle_comments_button = wait.until(ec.element_to_be_clickable((By.CSS_SELECTOR, '#toggle-button > div')))
        toggle_comments_button.click()

        time.sleep(2)

        # Add tags to the video
        tags_input = wait.until(ec.visibility_of_element_located((By.XPATH,
                                                                  '/html/body/ytcp-uploads-dialog/tp-yt-paper-dialog/div/ytcp-animatable[1]/ytcp-ve/ytcp-video-metadata-editor/div/ytcp-video-metadata-editor-advanced/div[4]/ytcp-form-input-container/div[1]/div/ytcp-free-text-chip-bar/ytcp-chip-bar/div/input')))
        tags_input.send_keys(keywords)
        time.sleep(1)

        next_button = driver.find_element(By.XPATH, '//*[@id="next-button"]')
        for i in range(3):
            next_button.click()
            time.sleep(1)

        public_button = wait.until(ec.element_to_be_clickable((By.NAME, 'PUBLIC')))
        # Click the "Public" button
        public_button.click()
        time.sleep(1)

        done_button = wait.until(ec.element_to_be_clickable((By.ID, "done-button")))
        done_button.click()
        time.sleep(3)
        close_button = wait.until(ec.element_to_be_clickable((By.XPATH, '//ytcp-button[@id="close-button"]')))

        # Click the "Kapat" button
        close_button.click()
        time.sleep(3)
    except Exception as e:
        print(e)
        time.sleep(500)


def clean_up(directory_path):
    """
    Removes a directory and its files.

    Args:
        directory_path (str): The path to the directory to be removed.
    """
    try:
        # Remove the directory and its contents
        shutil.rmtree(directory_path)
        print(f"Directory '{directory_path}' and its files have been successfully removed.")
    except OSError as e:
        print(f"Error: {e.filename} - {e.strerror}. Failed to remove the directory '{directory_path}'.")


if __name__ == "__main__":
    # Start ChromeDriver with options.
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=generate_chrome_options())
    driver.get("https://studio.youtube.com/")

    # Connect to the SQLite database
    conn = sqlite3.connect('processed_trends.db')
    cursor = conn.cursor()
    # Create a table to store processed trends if it doesn't exist
    cursor.execute('''CREATE TABLE IF NOT EXISTS trends (trend_name text)''')
    conn.commit()
    # Get Trends.
    trends = TrendReq().trending_searches(pn='united_states')

    for query in trends.iloc[:, 0]:
        ori_query = query
        query, summary = get_wikipedia_summary(ori_query)
        # Check if the trend has already been processed
        cursor.execute("SELECT * FROM trends WHERE trend_name=?", (query,))
        result = cursor.fetchone()
        if result:
            print(f"{query} ")

        elif result is None and summary:
            # Process the trend
            print(f"Beginning process for {query}.")
            print(f"Retrieving wikipedia data.")
            ori_query = query
            print(f"Retrieved wikipedia data."),
            print(f"{ori_query} has been replaced: New page title: {query}")
            workspace_path, audio_path, video_path, audio_dir, video_dir, synced_images_dir, images_dir = create_workspace()
            if summary:
                # Create audio
                language = "en"
                speech = gTTS(text=summary, lang=language, slow=False)
                os.makedirs(os.path.dirname(audio_path), exist_ok=True)
                speech.save(audio_path)
                audio = mp.AudioFileClip(audio_path)
                duration = audio.duration
                images_count = round(duration / 5)
                # End of audio process
                print("Photos download starts. You may see some errors. Ignore them.")
                download_images()
                sync_images()
                create_video()
                shortened_tags_result = short_keywords(generate_keywords(summary))
                upload_video_youtube(file_path=video_path, description=summary, title=query,
                                     keywords=shortened_tags_result)

                # Store the processed trend in the database
                cursor.execute("INSERT INTO trends VALUES (?)", (query,))
                conn.commit()

    # Close the database connection
    conn.close()
    clean_up(os.path.join(os.getcwd(), "workspace"))
