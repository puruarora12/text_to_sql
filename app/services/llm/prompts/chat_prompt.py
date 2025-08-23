from app.services.llm.prompts import prompt


@prompt()
def chat_prompt(**kwargs) -> str:
    """
    This prompt is used to chat with the LLM.

    You can use the kwargs to pass in data that will be used to generate the prompt.
    
    For example, if you want to pass in a list of messages, you can do the following:
    ```python
    chat_prompt(example_variable="test")
    ```

    You can then use the example_variable in the prompt like this:
    ```
    return [
        {"role": "system", "content": "Your name is %(name)s."} % kwargs
    ]
    ```
    """
    return [
        {"role": "system", "content": "You are a helpful assistant."},
    ]
