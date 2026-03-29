from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def main():
    print("Hello from server!")
    return "Hello from server!"


if __name__ == "__main__":
    main()
