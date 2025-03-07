import dagger
import asyncio

async def simple_pipeline():
    """A simple Dagger pipeline demonstrating basic container operations."""
    async with dagger.Connection() as client:
        # Start with a Python container
        container = client.container().from_("python:3.11-slim")
        
        # Install some basic tools
        container = (
            container
            .with_exec(["apt-get", "update"])
            .with_exec(["apt-get", "install", "-y", "curl", "git"])
        )
        
        # Create a simple Python script
        script = """
import time
print("Starting countdown...")
for i in range(5, 0, -1):
    print(f"{i}...")
    time.sleep(1)
print("Blast off! 🚀")
"""
        
        # Add the script to the container
        container = container.with_new_file("/app/countdown.py", script)
        
        # Run the script
        result = await container.with_exec(["python", "/app/countdown.py"]).stdout()
        
        print("Pipeline output:")
        print(result)

if __name__ == "__main__":
    asyncio.run(simple_pipeline()) 