import chainlit as cl
import speech_recognition as sr
from pydub import AudioSegment
from io import BytesIO
from langchain_community.chat_models import ChatOllama
from src.create_chain_retrievers import create_chain_retriever
from src.process_user_files import handle_files_from_audio_message
from src.generate_images  import generate_image
from src.search_wikipedia_queries import search_wikipedia_query
from src.topic_classifier import classify_intent
from src.scrape_links import scrape_link
from src.search_duckduckgo_queries import agent_results_text
from src.process_text_to_speech import speak_async
from groq import AsyncGroq

api_key = os.environ['Groq_API_KEY']

client = AsyncGroq(api_key=api_key)
import os
from dotenv import load_dotenv

load_dotenv()

base_url = os.getenv('BASE_URL')

AudioSegment.ffmpeg = r"C:\ffmpeg\bin\ffmpeg.exe"

async def process_audio_chunk(audio_chunk: cl.AudioChunk) -> BytesIO:
    """
    Handles incoming audio chunks and stores them in a buffer for further processing.

    Args:
        chunk (cl.AudioChunk): The audio data to process.

    Returns:
        BytesIO: The buffer containing the audio data.
    """
    if audio_chunk.isStart:
        buffer = BytesIO()
        buffer.name = f"input_audio.{audio_chunk.mimeType.split('/')[1]}"
        cl.user_session.set("audio_buffer", buffer)
        cl.user_session.set("audio_mime_type", audio_chunk.mimeType)

    audio_buffer = cl.user_session.get("audio_buffer")
    audio_buffer.write(audio_chunk.data)
    
    return audio_buffer

async def convert_audio_to_wav(audio_buffer: BytesIO, mime_type: str) -> BytesIO:
    """
    Converts audio data to WAV format.

    Args:
        audio_buffer (BytesIO): The buffer containing audio data.
        mime_type (str): The MIME type of the audio.

    Returns:
        BytesIO: The buffer containing the WAV audio data.
    """
    if audio_buffer is not None:
        audio_buffer.seek(0)
        with open("test_audio.wav", "wb") as f:
            f.write(audio_buffer.getbuffer())
        # audio_file = audio_buffer.read()
        audio_segment = AudioSegment.from_file_using_temporary_files(audio_buffer, 
                                            format=mime_type.split('/')[1])
        buffer_wav = BytesIO()
        audio_segment.export(buffer_wav, format='wav')
        buffer_wav.seek(0)
    else:
        print("No audio data found in the user session.")
    
    return buffer_wav

async def audio_answer(elements: list, model_name: str) -> None:
    """
    Transcribes audio input, processes the message, and generates a response.

    Args:
        elements (list): Additional elements like files or images that affect the response.
        model_name (str): The name of the language model used for generating responses.

    Returns:
        None
    """
    recognizer = sr.Recognizer()
    audio_buffer: BytesIO = cl.user_session.get("audio_buffer")
    audio_buffer.seek(0)
    mime_audio_message = cl.user_session.get("audio_mime_type")
    audio_file = audio_buffer.read()

    input_audio_el = cl.Audio(
        mime=mime_audio_message, content=audio_file, name=audio_buffer.name
    )
    await cl.Message(
        author="You",
        type="user_message",
        content="",
        elements=[input_audio_el, *elements],
    ).send()

    audio_wav = await convert_audio_to_wav(audio_buffer=audio_buffer, mime_type=mime_audio_message)

    try:
        with sr.AudioFile(audio_wav) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.2)  
            audio = recognizer.record(source)  
            transcription = recognizer.recognize_google(audio, language="en_EN")
            print('transcription: ', transcription)

        chain = await create_chain_retriever(texts=transcription, source_prefix="text/plain")
        
        await cl.Message(content=transcription, elements=elements).send()
        
        if elements:           
              
            for file in elements:
                
                if file.mime == "text/csv":
                    await handle_files_from_audio_message(elements=elements, user_message=transcription)
                
                elif file.mime.startswith("image/"):
                    await handle_files_from_audio_message(elements=elements, user_message=transcription)
                
                else: 
                    cb = await handle_files_from_audio_message(elements=elements, user_message=transcription) 
                    
                    response = await chain.ainvoke(transcription, callbacks=[cb])
                    answer = response["answer"]
                    
                    await cl.Message(content=answer).send()
                    await speak_async(answer=answer)
                       
        else:
            intent = await classify_intent(user_message=transcription)

            if 'image' in intent:
                print('Your intent is: ', intent)
                                
                await cl.Message(content="🖼️ Image Generation Selected! 🖼️ \n You've chosen to generate an image. This might take 1 or 2 minutes.").send()
                
                generated_image_path = await generate_image(user_message=transcription)
                image_element = cl.Image(name="Generated Image", path=str(generated_image_path))
                
                await cl.Message(content="✨ Here you go! ✨ \n Here’s the generated image!", elements=[image_element]).send()
            
            elif 'wikipedia' in intent:
                print('Your intent is: ', intent)
                
                query = transcription.split(' ')[1:]
                keywords_string = ''.join(query)
                
                await cl.Message(content="🔍 Wikipedia Search Selected! 🔍\n You've chosen to search on Wikipedia. Please enter your topic in the form of keywords below!").send()
                
                url, content = await search_wikipedia_query(user_message=keywords_string)
                formatted_results = f"🔗 **Source Link:** {url}\n\n📖 **Content:** {content}"
                
                await cl.Message(content=formatted_results).send()
            
            elif 'scraper' in intent:
                print('Your intent is: ', intent)
                
                scraped_link = await scrape_link(user_message=transcription)
                link_element = cl.File(name='Extracted link', path=scraped_link)
                
                await cl.Message(content='🎉 Your link has been successfully extracted 🎉.\n Click here to access the content directly!: ', elements=[link_element]).send()
 
            elif 'search' in intent:
                print('Your intent is: ', intent)
                                
                await cl.Message(content="🌐 DuckDuckGo Search Selected! 🌐 \n You've chosen to search on the DuckDuckGo Web Browser.\n The first 10 links will be displayed.").send()
                
                search_results = await agent_results_text(user_message=transcription)
                formatted_results = ""
                
                for index, result in enumerate(search_results[:10], start=1):  
                    title = result['title']
                    href = result['href']
                    body = result['body']
                    formatted_results += f"{index}. **Title:** {title}\n**Link:** {href}\n**Description:** {body}\n\n"
                
                await cl.Message(content=formatted_results).send()
                                
            elif 'chat' in intent:
                print('Your audio intent is: ', intent)

                # print('Your audio intent is: ', intent)
                
                # model = ChatOllama(model=model_name, base_url=base_url) 
                # answer = await model.ainvoke(transcription)
                
                # await cl.Message(content=answer.content).send()  
                chat_history = cl.user_session.get('chat_history', [])
                model = "llama3-8b-8192"
                streaming = True
                temperature = 0.5
                max_tokens = 1024

                stream = await client.chat.completions.create(
                    messages=chat_history,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=streaming,
                )

                msg = cl.Message(content="")

                full_response = ""
                if streaming:
                    async for chunk in stream:
                        content = chunk.choices[0].delta.content
                        if content:
                            full_response += content
                            await msg.stream_token(content)
                    await msg.send()
                else:
                    response = await stream
                    full_response = response.choices[0].message.content
                    await cl.Message(content=full_response).send()

                chat_history.append({"role": "assistant", "content": full_response})

                cl.user_session.set("chat_history", chat_history)
                await speak_async(answer=full_response) 

    except sr.UnknownValueError:
        
        await cl.Message(content="Impossible to recognize the input audio message").send()



