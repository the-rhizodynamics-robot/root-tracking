docker run -it --rm -v /home/iwtwb8/data/to_unspool/:/app/input   -v ~/:/app/output   r
oot-tracking-env   python /app/code/unspool_stabilize.py --input_path /app/input --output_path /app/output

maybe try this to not have permission issues:
docker run -it --rm \
  -u $(id -u):$(id -g) \
  -v /path/to/input:/app/input \
  -v /path/to/output:/app/output \
  root-tracking-env \
  python /app/code/script.py --input_path /app/input --output_path /app/output
  
Let's setup like:

project_name/
├── README.md
├── setup.py
├── requirements.txt
├── .dockerignore
├── .gitignore
├── Dockerfile
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── module1.py
│   └── module2.py
└── tests/
    ├── __init__.py
    ├── test_module1.py
    └── test_module2.py


To do:

set up github/workflows'


Move code to image.


docker run -it --rm -p 8888:8888 jupyterlab

draft python runner (webbrowser is built in). Maybe consider singularity?

Requirements:

-Python 3.X

-Docker


