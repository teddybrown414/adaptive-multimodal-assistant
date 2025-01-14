import chainlit as cl
from pandas import DataFrame
from langchain_community.chat_models import ChatOllama
from src.generate_images import generate_image
from src.search_wikipedia_queries import search_wikipedia_query
from src.topic_classifier import classify_intent
from src.scrape_links import scrape_link
from src.search_duckduckgo_queries import agent_results_text
from groq import AsyncGroq

from src.text_summarization import summarize_text

import requests
import json

import os
from dotenv import load_dotenv

api_key = os.environ['GROQ_API_KEY']

client = AsyncGroq(api_key=api_key)
load_dotenv()

base_url = os.getenv('BASE_URL')


async def process_user_message(user_message: cl.Message, model_name: str) -> None:
    """
    Processes a user message and provides a response using a language model or performs specific actions based on the intent.

    Args:
        user_message (cl.Message): The message sent by the user to be processed.
        model_name (str): The model selected with the chat_profile choice.

    Workflow:
    - If no active chain exists in the user session:
        1. Classifies the user's intent (image generation, Wikipedia search, web scraping, or general chat).
        2. Executes the corresponding action:
            - Generates an image (if 'image' intent).
            - Searches Wikipedia (if 'wikipedia' intent).
            - Scrapes content from a URL (if 'scraper' intent).
            - Searches using DuckDuckGo (if 'search' intent).
            - Answers a general chat question (if 'chat' intent).

    - If an active chain exists:
        - Processes the message using the existing chain and retrieves the response and source documents.
    """
    chain = cl.user_session.get("chain")
    user_message = user_message.content.strip()
    
    chat_history = cl.user_session.get("chat_history", [])

    chat_history = chat_history[-10:]

    print(chat_history)

    if chain is None:
        intent = await classify_intent(user_message=user_message)
        
        if 'image' in intent:
            print('Your intent is: ', intent)
            chat_history.append({"role": "user", "content": user_message})
            
            await cl.Message(content="🖼️ Image Generation Selected! 🖼️ \n You've chosen to generate an image. This might take 1 or 2 minutes.").send()
            
            generated_image_path = await generate_image(user_message=user_message)
            image_element = cl.Image(name="Generated Image", path=generated_image_path, size='large')
            
            await cl.Message(content="✨ Here you go! ✨ \n Here’s the generated image!", elements=[image_element]).send()

            chat_history.append({'role': 'assistant', 'content': f'Generated image path: {generated_image_path}'})

            cl.user_session.set("chat_history", chat_history)
                        
        elif 'wikipedia' in intent:
            print('Your intent is: ', intent)
            chat_history.append({"role": "user", "content": user_message})

            query = user_message.split(' ')[1:]
            keywords_string = ''.join(query)
            
            await cl.Message(content="🔍 Wikipedia Search Selected! 🔍\n You've chosen to search on Wikipedia. Please enter your topic in the form of keywords below!").send()
            
            url, content = await search_wikipedia_query(user_message=keywords_string)
            formatted_results = f"🔗 **Source Link:** {url}\n\n📖 **Content:** {content}"
            
            await cl.Message(content=formatted_results).send()

            summarized_result = await summarize_text(formatted_results, 5)
            
            chat_history.append({'role': 'assistant', 'content': summarized_result})

            cl.user_session.set("chat_history", chat_history)
        
        elif 'scraper' in intent:
            print('Your intent is: ', intent)
            chat_history.append({"role": "user", "content": user_message})

            scraped_link = await scrape_link(user_message=user_message)
            link_element = cl.File(name='Extracted link', path=str(scraped_link))
            
            await cl.Message(content='🎉 Your link has been successfully extracted 🎉.\n Click here to access the content directly!: ', elements=[link_element]).send()

            chat_history.append({'role': 'assistant', 'content': f"Your link has been extracted: {scraped_link}"})

            cl.user_session.set("chat_history", chat_history)
            
        elif 'search' in intent:
            print('Your intent is: ', intent)
            chat_history.append({"role": "user", "content": user_message})
                        
            await cl.Message(content="🌐 DuckDuckGo Search Selected! 🌐 \n You've chosen to search on the DuckDuckGo Web Browser.\n The first 5 links will be displayed.").send()
            search_results = await agent_results_text(user_message=user_message)

            formatted_results = ""
            for index, result in enumerate(search_results[:10], start=1):  
                title = result['title']
                href = result['href']
                body = result['body']
                formatted_results += f"{index}. **Title:** {title}\n**Link:** {href}\n**Description:** {body}\n\n"

            await cl.Message(content=formatted_results).send()

            summarized_result = await summarize_text(formatted_results, 5)
            
            chat_history.append({'role': 'assistant', 'content': summarized_result})

            cl.user_session.set("chat_history", chat_history)
                          
        elif 'chat' in intent:
            print('Your intent is: ', intent)

            chat_history.append({"role": "user", "content": user_message})

            # msg = cl.Message(content="")

            # Append the new user message to the chat history

            # Prepare the request payload
            # payload = {
            #     "model": model_name,
            #     "messages": chat_history,
            #     "stream": True  # Enable streaming
            # }

            # # Send the request to the Ollama API
            # response = requests.post(f"{base_url}/api/chat", json=payload, stream=True)

            # # Initialize an empty string to accumulate the response
            # accumulated_response = ""

            # # Stream the response token by token
            # for line in response.iter_lines():
            #     if line:
            #         # Decode the line and parse the JSON
            #         data = line.decode('utf-8')
            #         response_data = json.loads(data)
            #         # Append the new token to the accumulated response
            #         accumulated_response += response_data['message']['content']
            #         display_content = response_data['message']['content']
            #         # Send the current accumulated response to Chainlit
            #         await msg.stream_token(display_content)
                
            # await msg.update()

            # chat_history.append({"role": "assistant", "content": accumulated_response})

            # cl.user_session.set("chat_history", chat_history)
            ########## OLLAMA #############
            # model = ChatOllama(model=model_name, base_url=base_url, stream=True) 
            # answer = await model.ainvoke(user_message)
            
            # await cl.Message(content=answer.content).send()

            ########## Groq #################

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

            # requests.

            chat_history.append({"role": "assistant", "content": full_response})

            cl.user_session.set("chat_history", chat_history)

    else:
        if type(chain) == str:
            pass
            
        elif type(chain) == DataFrame:
            pass

        else:  
            response = await chain.ainvoke(user_message)
            answer = response["answer"]
            
            await cl.Message(content=answer).send()

            chat_history.append({"role": "user", "content": user_message})
            chat_history.append({'role': 'assistant', 'content': answer})

            cl.user_session.set("chat_history", chat_history)
            
