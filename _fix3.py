import re

with open('d:/DialecticEngine/tools/docker_tools.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

for i in range(len(lines)):
    line = lines[i]

    # Line 62: Docker daemon auth failure
    if 'Docker daemon \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4' in line:
        lines[i] = line.replace(
            'Docker daemon \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4',
            'Docker daemon 未登录（认证失败）'
        )
        print(f'Fixed line {i+1}: auth failure')

    # Line 115: Windows install
    if '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 Windows \u03b4\u03b4' in line:
        lines[i] = line.replace(
            '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 Windows \u03b4\u03b4',
            '运行安装程序（Windows 版）'
        )
        print(f'Fixed line {i+1}: windows install')

    # Line 128: 20-40 seconds
    if '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 \u03b4\u03b4 20-40 \u03b4\u03b4' in line:
        lines[i] = line.replace(
            '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 \u03b4\u03b4 20-40 \u03b4\u03b4',
            '等待托盘图标变为绿色（约 20-40 秒）'
        )
        print(f'Fixed line {i+1}: 20-40 seconds')

    # Line 139: prompt intro
    if '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4:' in line:
        lines[i] = line.replace(
            '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4:',
            '请完成上述操作后输入选项:'
        )
        print(f'Fixed line {i+1}: prompt intro')

    # Line 140: r/R done
    if '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4' in line and 'r/R' in line:
        lines[i] = line.replace('\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4', '已完成，重新检测')
        print(f'Fixed line {i+1}: r/R')

    # Line 141: s/S skip
    if '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 milvus' in line:
        lines[i] = line.replace(
            '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 milvus',
            '跳过检查，直接启动（milvus 功能可能不可用）'
        )
        print(f'Fixed line {i+1}: s/S')

    # Line 148: hard stop
    if '[\u03b4\u03b4\u03b4\u03b4\u03b4]' in line and '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4' in line:
        lines[i] = re.sub(
            r'\[\u03b4+\] \u03b4+\u03b4\u03b4\u03b4+\u03b4\u03b4+\u03b4+\u03b4+',
            '[硬停止] 已重试多次仍失败',
            line
        )
        print(f'Fixed line {i+1}: hard stop')

    # Line 150: manual fix
    if '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 \u03b4\u03b4 Docker daemon' in line:
        lines[i] = line.replace(
            '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 \u03b4\u03b4 Docker daemon \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4',
            '请手动解决 Docker 问题后再次运行'
        )
        print(f'Fixed line {i+1}: manual fix')

    # Line 151: q/r prompt
    if '\u03b4\u03b4 q' in line:
        lines[i] = line.replace('\u03b4\u03b4 q \u03b4\u03b4\u03b4\u03b4\u03b4 r \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4: ',
                                '输入 q 退出，或输入 r 再试一次: ')
        print(f'Fixed line {i+1}: q/r prompt')

    # Line 164: skipped
    if '\u03b4\u03b4 Docker daemon' in line and 'milvus' in line:
        lines[i] = line.replace(
            '\u03b4\u03b4 Docker daemon \u03b4\u03b4milvus \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4',
            '已跳过 Docker 检查，milvus 功能将不可用'
        )
        print(f'Fixed line {i+1}: skipped')

    # Line 169: invalid
    if '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 r / s / q' in line:
        lines[i] = line.replace(
            '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 r / s / q',
            '无效输入，请输入 r / s / q'
        )
        print(f'Fixed line {i+1}: invalid')

    # Line 391: logged in
    if 'Docker daemon \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4' in line:
        lines[i] = line.replace(
            'Docker daemon \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4',
            'Docker 已登录'
        )
        print(f'Fixed line {i+1}: logged in')

    # Line 395: not logged
    if 'Docker daemon \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 docker pull' in line:
        lines[i] = line.replace(
            'Docker daemon \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 docker pull \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 Docker Desktop \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4: docker login',
            'Docker 未登录或认证已过期（docker pull 测试失败）。请运行 docker login'
        )
        print(f'Fixed line {i+1}: not logged')

    # Line 397: not logged CLI
    if 'Docker CLI \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 pull' in line:
        lines[i] = line.replace(
            'Docker CLI \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 pull \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 Docker Hub',
            'Docker CLI 未登录，但 pull 可能仍可用（公开镜像）'
        )
        print(f'Fixed line {i+1}: not logged CLI')

    # Line 398: note
    if '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4' in line:
        lines[i] = line.replace(
            '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4',
            '未登录，匿名访问公开镜像'
        )
        print(f'Fixed line {i+1}: note')

    # Lines 485, 487, 488: 已安装/未安装
    if "'Docker CLI: {" in line and "\u03b4\u03b4\u03b4'" in line:
        lines[i] = re.sub(r"'已安装 \(' \+", "'已安装 (' +", line)
        lines[i] = lines[i].replace("\u03b4\u03b4\u03b4 if cli_found else '\u03b4\u03b4\u03b4\u03b4\u03b4'", "已安装 if cli_found else '未安装'")
        print(f'Fixed line {i+1}: CLI parts')

    if 'Docker Desktop' in line and "\u03b4\u03b4\u03b4'" in line:
        lines[i] = lines[i].replace("{'已安装' if desktop_found else '\u03b4\u03b4\u03b4\u03b4'}", "{'已安装' if desktop_found else '未安装'}")
        print(f'Fixed line {i+1}: Desktop parts')

    if 'WSL2:' in line and "\u03b4\u03b4\u03b4'" in line:
        lines[i] = lines[i].replace("{'已安装' if wsl_found else '\u03b4\u03b4\u03b4\u03b4'}", "{'已安装' if wsl_found else '未安装'}")
        print(f'Fixed line {i+1}: WSL2 parts')

    # Lines 490, 492: suggestions
    if '\u03b4\u03b4\u03b4\u03b4\u03b4: \u03b4\u03b4 Docker Desktop' in line:
        lines[i] = lines[i].replace(
            '\u03b4\u03b4\u03b4\u03b4\u03b4: \u03b4\u03b4 Docker Desktop for Windows (\u03b4\u03b4 WSL2)',
            '建议: 安装 Docker Desktop for Windows (需要 WSL2)'
        )
        print(f'Fixed line {i+1}: suggestion Desktop')

    if '\u03b4\u03b4\u03b4\u03b4\u03b4: \u03b4\u03b4 Docker Engine' in line:
        lines[i] = lines[i].replace(
            '\u03b4\u03b4\u03b4\u03b4\u03b4: \u03b4\u03b4 Docker Engine for your OS',
            '建议: 安装 Docker Engine for your OS'
        )
        print(f'Fixed line {i+1}: suggestion Engine')

    # Line 581: download url
    if 'Docker Desktop for Windows\u03b4' in line and 'https://' in line:
        lines[i] = lines[i].replace(
            'Docker Desktop for Windows\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 https://docs.docker.com/desktop/install/windows-install/ \u03b4\u03b4\u03b4\u03b4',
            'Docker Desktop 未安装。请从 https://docs.docker.com/desktop/install/windows-install/ 下载'
        )
        print(f'Fixed line {i+1}: download url')

    # Line 599: launched observation
    if 'Docker Desktop \u03b4 ' in line and 'check_docker_daemon' in line:
        lines[i] = lines[i].replace(
            'Docker Desktop \u03b4 {desktop_exe} \u03b4\u03b4\u03b4\u03b4\u03b4 20-40 \u03b4\u03b4\u03b4\u03b4 check_docker_daemon() \u03b4\u03b4 daemon \u03b4\u03b4',
            "Docker Desktop 已从 {desktop_exe} 启动。等待 20-40 秒后调用 check_docker_daemon() 确认 daemon 就绪"
        )
        print(f'Fixed line {i+1}: launched observation')

    # Line 606: manual launch
    if '\u03b4\u03b4\u03b4\u03b4 Docker Desktop' in line:
        lines[i] = lines[i].replace(
            '\u03b4\u03b4\u03b4\u03b4 Docker Desktop\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4',
            '无法启动 Docker Desktop。请手动从开始菜单启动'
        )
        print(f'Fixed line {i+1}: manual launch')

with open('d:/DialecticEngine/tools/docker_tools.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

# Verify
with open('d:/DialecticEngine/tools/docker_tools.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()
remaining = content.count('\u03b4')
print(f'Done. Remaining \\u03b4 chars: {remaining}')
print(f'File size: {len(content)} bytes')
