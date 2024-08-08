import numpy as np
import os
import datetime
import random
from scipy.io import wavfile
import ChatTTS
import subprocess
import torch
import whisper
from openai import OpenAI
import siot
import time
import pygame

# Initialize pygame for audio playback
pygame.mixer.init()

# Set the model type for Whisper (options: "base", "small", "large", "medium")
model_type = "small"
# Set the duration for audio recording
duration = 10

# Define a global flag for state management
global state_flag
state_flag = None

# MQTT message callback function to update the state based on the received message
def on_message_callback(client, userdata, msg):
    global state_flag 
    if msg.topic == "siot/sys":
        if msg.payload.decode() == "start":
            state_flag = 'start'
        elif msg.payload.decode() == "1":
            state_flag = 'record'
        elif msg.payload.decode() == "2":
            state_flag = 'transcribe'
        elif msg.payload.decode() == "3":
            state_flag = 'playback'
        elif msg.payload.decode() == "stop":
            state_flag = 'stop'

# Initialize siot (MQTT) with provided credentials and settings
siot.init(client_id="7194728385057718", server="10.1.2.3", port=1883, user="siot", password="dfrobot")
siot.connect()
siot.loop()
siot.set_callback(on_message_callback)
siot.subscribe(topic="siot/sys")

# Function to record audio using the 'arecord' command
def record_audio(duration, filename):
    command = f"arecord -f cd -d {duration} -t wav {filename}"
    subprocess.run(command, shell=True)
    return filename

# Function to transcribe audio using the Whisper model
def transcribe_audio(filename, model_type):
    model = whisper.load_model(model_type)
    result = model.transcribe(filename)
    return result["text"]

# Function to convert text to speech using ChatTTS
def text_to_speech_sub(text):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    random_number = 1996  # Fixed seed for voice consistency
    command = f"chattts '{text}' -s {random_number} -o outputs/{timestamp}-{random_number}.wav"
    subprocess.run(command, shell=True)
    output_file = f'outputs/{timestamp}-{random_number}.wav'
    print(f"WAV file saved as '{output_file}'")
    return output_file

# Function to generate an answer using the DeepSeek API
def answer_the_question_deepseek(user_question):
    API_KEY = 'sk-efef2be62a99432b8f3fa5272df98a0b'
    client = llm_api(api_key=API_KEY,
            base_url="https://api.deepseek.com",
            model="deepseek-chat")
    text = client.call(user_question, prompt_version = 'deepseek')
    text = client.call(text, prompt_version = 'deepseek_TN')
    print("Answer is: " + text)
    return text

# Function to generate an answer using the OpenAI API
def answer_the_question_ollama(user_question):
    # Initialize the OpenAI client
    client = OpenAI(
        base_url='http://localhost:11434/v1',
        api_key='ollama'  # required, but unused
    )
    
    # Generate a response
    response = client.chat.completions.create(
        model="deepseek-v2",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Please converse with me as Socrates, answering my question with counterquestions only. Limit your reply to 30 characters, using only commas and periods. Convert numbers to text. My question is: " + user_question}
        ]
    )
    
    text = response.choices[0].message.content
    print("Answer: " + text)
    return text

# Function to check the state flag and stop audio if necessary
def check_state_and_stop():
    global state_flag
    if state_flag == 'stop':
        pygame.mixer.music.stop()
        return True  # Return a flag indicating to stop further operations
    return False  # Return a flag indicating to continue execution

# Function to play audio with state check
def play_with_state_check(file):
    pygame.mixer.music.load(file)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
        if check_state_and_stop():  # Check if the state flag is 'stop', and stop if necessary
            return True
    return False

# Function to play music
def play_music(file):
    pygame.mixer.music.stop()
    pygame.mixer.music.load(file)
    pygame.mixer.music.play()

# Main loop to handle different states based on the flag
while True:
    if state_flag == 'stop':  # Idle state
        play_music('5s.wav')
        state_flag = None

    elif state_flag == 'start':  # Start state
        play_music('idel.wav')
        state_flag = None

    elif state_flag == 'record':  # Record audio state
        pygame.mixer.music.stop()
        if play_with_state_check('waitingforcalling.wav'):
            state_flag = None
        else:
            pygame.mixer.music.stop()
            if not play_with_state_check('start.wav'):
                siot.publish(topic="siot/mess", data="1")
            state_flag = None

    elif state_flag == 'transcribe':  # Transcribe audio state
        audio = record_audio(10, "question.wav")
        siot.publish(topic="siot/mess", data="2")  
        speech_to_text = transcribe_audio(audio, model_type)
        user_input = speech_to_text
        print("User question: " + user_input)
        answer = answer_the_question_ollama(user_input)
        output_path = text_to_speech_sub(answer) 
        siot.publish(topic="siot/mess", data="3") 
        state_flag = None
        
    elif state_flag == 'playback':  # Playback audio state
        play_music(output_path)
        state_flag = None
