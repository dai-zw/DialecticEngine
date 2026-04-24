with open('d:/DialecticEngine/tools/docker_tools.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

fixes = [
    ('Docker daemon \u03b4\u03b5\u03b4\u03b5\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4', 'Docker daemon 未登录（认证失败）'),
    ('\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 Windows \u03b4\u03b4', '运行安装程序（Windows 版）'),
    ('\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 \u03b4\u03b4 20-40 \u03b4\u03b4', '等待托盘图标变为绿色（约 20-40 秒）'),
    ('\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4:', '请完成上述操作后输入选项:'),
    ('\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4', '已完成，重新检测'),
    ('\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 milvus \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4', '跳过检查，直接启动（milvus 功能可能不可用）'),
    ('[\u03b4\u03b4\u03b4\u03b4\u03b4] \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4', '已重试多次仍失败'),
    ('\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 \u03b4\u03b4 Docker daemon \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4', '请手动解决 Docker 问题后再次运行'),
    ('\u03b4\u03b4 q \u03b4\u03b4\u03b4\u03b4\u03b4 r \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4: ', '输入 q 退出，或输入 r 再试一次: '),
    ('\u03b4\u03b4 Docker daemon \u03b4\u03b4milvus \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4', '已跳过 Docker 检查，milvus 功能将不可用'),
    ('\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 r / s / q', '无效输入，请输入 r / s / q'),
    ('Docker daemon \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 \u03b4 Docker Hub', 'Docker 已登录。已认证: Docker Hub'),
    ('Docker daemon \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 docker pull \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 Docker Desktop \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4: docker login', 'Docker 未登录或认证已过期（docker pull 测试失败）。请运行 docker login'),
    ('Docker CLI \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 pull \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 Docker Hub \u03b4\u03b4\u03b4\u03b4', 'Docker CLI 未登录，但 pull 可能仍可用（公开镜像）'),
    ('\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4', '未登录，匿名访问公开镜像'),
    ("f\"Docker CLI: {'\u03b4\u03b4\u03b4' (\\' + cli_version.split(' version ')[1].split(',')[0] + ')' if cli_version else '\u03b4\u03b4\u03b4\u03b4\u03b4'} if cli_found else '\u03b4\u03b4\u03b4\u03b4\u03b4'}\"",
     "f\"Docker CLI: {'已安装 (' + cli_version.split(' version ')[1].split(',')[0] + ')' if cli_version else '已安装' if cli_found else '未安装'}\""),
    ("f\"Docker Desktop: {'\u03b4\u03b4\u03b4' if desktop_found else '\u03b4\u03b4\u03b4\u03b4'}\")",
     "f\"Docker Desktop: {'已安装' if desktop_found else '未安装'}\")"),
    ("f\"WSL2: {'\u03b4\u03b4\u03b4' if wsl_found else '\u03b4\u03b4\u03b4\u03b4'}\")",
     "f\"WSL2: {'已安装' if wsl_found else '未安装'}\")"),
    ('\u03b4\u03b4\u03b4\u03b4\u03b4: \u03b4\u03b4 Docker Desktop for Windows (\u03b4\u03b4 WSL2)',
     '建议: 安装 Docker Desktop for Windows (需要 WSL2)'),
    ('\u03b4\u03b4\u03b4\u03b4\u03b4: \u03b4\u03b4 Docker Engine for your OS',
     '建议: 安装 Docker Engine for your OS'),
    ('Docker Desktop for Windows\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 https://docs.docker.com/desktop/install/windows-install/ \u03b4\u03b4\u03b4\u03b4',
     'Docker Desktop 未安装。请从 https://docs.docker.com/desktop/install/windows-install/ 下载'),
    (f'Docker Desktop \u03b4 {desktop_exe} \u03b4\u03b4\u03b4\u03b4\u03b4 20-40 \u03b4\u03b4\u03b4\u03b4 check_docker_daemon() \u03b4\u03b4 daemon \u03b4\u03b4',
     f'Docker Desktop 已从 {desktop_exe} 启动。等待 20-40 秒后调用 check_docker_daemon() 确认 daemon 就绪'),
    ('\u03b4\u03b4\u03b4\u03b4 Docker Desktop\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4',
     '无法启动 Docker Desktop。请手动从开始菜单启动'),
]

applied = 0
for bad, good in fixes:
    if bad in content:
        content = content.replace(bad, good)
        applied += 1
        print(f'Fixed: {repr(bad[:50])}')

# Line 139 is tricky - partial fix needed
# "  ���˳�????  "  -> "  请完成上述操作后输入选项:    "
partial = '\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4 \u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4\u03b4'
if partial in content:
    content = content.replace(partial, '请完成上述操作后输入选项:    ')
    applied += 1
    print('Fixed partial line 139')

print(f'Total applied: {applied}')
remaining = content.count('\u03b4')
print(f'Remaining \u03b4 chars: {remaining}')

with open('d:/DialecticEngine/tools/docker_tools.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Written.')
