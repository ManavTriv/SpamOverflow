FROM ubuntu:22.04
# Installing dependencies for running a python application
RUN apt-get update && apt-get install -y python3 python3-pip wget
# Install pipenv
RUN pip3 install poetry
# Setting the working directory
WORKDIR /spamoverflow
# Install pipenv dependencies
COPY pyproject.toml ./
RUN poetry install --no-root
# Install psycopg2 for PostgreSQL support
RUN poetry add psycopg2-binary
# Copying our application into the container
COPY spamoverflow spamoverflow
# Get the version of spamhammer that matches the architecture of the container
RUN dpkg --print-architecture | grep -q "amd64" && export SPAMHAMMER_ARCH="amd64" || export SPAMHAMMER_ARCH="arm64" && wget https://github.com/CSSE6400/SpamHammer/releases/download/v1.0.0/spamhammer-v1.0.0-linux-${SPAMHAMMER_ARCH} -O spamoverflow/spamhammer.exe && chmod +x spamoverflow/spamhammer.exe
# Running our application
CMD ["poetry", "run", "flask", "--app", "spamoverflow", "run", "--host", "0.0.0.0", "--port", "8080"]