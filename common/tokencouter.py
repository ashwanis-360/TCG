import tiktoken

def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613") -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    # constants per message overhead (3 tokens for role/content tags, +1 if name present)
    tokens_per_msg = 3
    tokens_per_name = 1
    num_tokens = 0
    for msg in messages:
        num_tokens += tokens_per_msg
        for key, val in msg.items():
            num_tokens += len(encoding.encode(val))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # assistant reply priming tokens
    return num_tokens
