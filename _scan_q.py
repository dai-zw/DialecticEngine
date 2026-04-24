with open('d:/DialecticEngine/tools/docker_tools.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

lines = content.split('\n')
for i, line in enumerate(lines):
    if '??' in line or '??' in line:
        print(f'{i+1}: {repr(line[:150])}')
