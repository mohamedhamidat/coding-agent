from setuptools import setup, find_packages

setup(
    name="coding-agent",
    version="0.1.0",
    description="Simple coding agent with multiple LLM providers (OpenAI, Claude, Ollama)",
    author="Mohamed Hamidat",
    author_email="mohamed.hamidat.uk@gmail.com",
    python_requires=">=3.8",
    packages=find_packages(),
    install_requires=[
        "litellm>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "coding-agent=main:main",
        ],
    },
)
