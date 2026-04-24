with open('d:/DialecticEngine/tools/docker_tools.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

fixes = [
    ('Docker CLI ???', 'Docker CLI 未安装'),
    ('Docker daemon δ????????', 'Docker daemon 未登录（认证失败）'),
    ('docker info ??)', 'docker info 成功)'),
    ('??: https://', '下载: https://'),
    ('????????Windows ??', '运行安装程序（Windows 版）'),
    ('??????? \'Use WSL', '安装过程中勾选 Use WSL'),
    ('(??)', '（推荐）'),
    ('???????????? Docker Desktop', '安装完成后从开始菜单启动 Docker Desktop'),
    ('??????????', '等待托盘图标变为绿色'),
    ('- ??????? \'Docker Desktop\'', '- 从开始菜单启动 Docker Desktop'),
    ('- ????????? 20-40 ??', '- 等待托盘图标变为绿色（约 20-40 秒）'),
    ('- ??? \'Sign In\' ?? Docker Hub ??', '- 右上角 Sign In 登录 Docker Hub 账号'),
    ('- ?????milvusdb/milvus????', '- 公开镜像（milvusdb/milvus）无需登录'),
    ('  ���˳�????  r/R  - ????????', '  请完成上述操作后输入选项:    r/R  - 已完成，重新检测'),
    ('  s/S  - ??????????milvus ???', '  s/S  - 跳过检查，直接启动（milvus 功能可能不可用）'),
    ('  q/Q  - ????', '  q/Q  - 退出程序'),
    ('[???] ??????', '[硬停止] 已重试多次仍失败'),
    ('  ���˳�? Docker daemon δ??????????', '  请手动解决 Docker 问题后再次运行程序。'),
    ('  ?? q ?????? r ����?: ', '  输入 q 退出，或输入 r 再试一次: '),
    ('  ??? Docker daemon δ��milvus ???????', '  已跳过 Docker 检查，milvus 功能将不可用'),
    ('  ���˳�???? r / s / q', '  无效输入，请输入 r / s / q'),
    ('Linux ?? dockerd ??', 'Linux 需要 dockerd 服务'),
    ('??: {os_name} | {docker_note}', '平台: {os_name} | {docker_note}'),
    ('if docker_note else f"??: {os_name}', 'if docker_note else f"平台: {os_name}'),
    ('docker_note else f"??: {os_name}', 'docker_note else f"平台: {os_name}'),
    ('Docker daemon δ��?????????  ? Docker Hub', 'Docker 已登录。已认证: Docker Hub'),
    ('Docker daemon δ��???????docker pull ???????? Docker Desktop ?????? docker login', 'Docker 未登录或认证已过期（docker pull 测试失败）。请运行 docker login'),
    ('Docker CLI ????? pull ??????Docker Hub ???', 'Docker CLI 未登录，但 pull 可能仍可用（公开镜像）'),
]

applied = 0
for bad, good in fixes:
    if bad in content:
        content = content.replace(bad, good)
        applied += 1
        print('Fixed:', repr(bad[:30]))

# Count remaining ?
remaining = content.count('??') + content.count('??')
print(f'Applied {applied} fixes. Remaining ?: {remaining}')

with open('d:/DialecticEngine/tools/docker_tools.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Written.')
