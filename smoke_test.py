from llama_cpp import Llama

llm = Llama(
    model_path="models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
    n_ctx=2048,
    n_batch=128,
    n_threads=4,
    verbose=False,
)

result = llm.create_chat_completion(
    messages=[{"role": "user", "content": "Say hello in one word."}],
    max_tokens=20,
)

print(result["choices"][0]["message"]["content"])