import sys
from dotenv import load_dotenv
from chat_discuss import discuss_strategy

# Subprocess wrapper to avoid atexit registration issues in daemon threads

if __name__ == "__main__":
    load_dotenv()

    if len(sys.argv) < 3:
        print("ERROR: Missing arguments. Usage: chat_discuss_cli.py <json_filename> <user_question>", file=sys.stderr)
        sys.exit(1)

    json_filename = sys.argv[1]
    user_question = sys.argv[2]

    result = discuss_strategy(json_filename, user_question)
    print(result)
