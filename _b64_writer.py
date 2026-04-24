import base64, sys

b64 = "77u/..."

with open("d:/DialecticEngine/tools/docker_tools.py", "wb") as f:
    f.write(base64.b64decode(b64))

print("done")
