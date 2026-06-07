# -*- coding: utf-8 -*-
"""
乐转站 Android APK 自动构建脚本
通过 GitHub Actions 云端构建，自动下载 APK

用法：python build_apk.py
需要：GitHub Personal Access Token（https://github.com/settings/tokens）
"""

import os
import sys
import time
import zipfile
import tempfile
import base64
import json
import urllib.request
import urllib.error

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_NAME = "picksound-build"
USER_AGENT = "APK-Builder/1.0"

def api_request(method, url, token, data=None):
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", USER_AGENT)
    if data:
        req.add_header("Content-Type", "application/json")
        return urllib.request.urlopen(req, json.dumps(data).encode()).read()
    return urllib.request.urlopen(req).read()

def get_username(token):
    data = json.loads(api_request("GET", "https://api.github.com/user", token))
    return data["login"]

def create_repo(token, username):
    print("[1/5] 创建 GitHub 仓库...")
    data = {
        "name": REPO_NAME,
        "private": False,
        "auto_init": False,
    }
    try:
        api_request("POST", "https://api.github.com/user/repos", token, data)
        print(f"  仓库: {username}/{REPO_NAME}")
    except urllib.error.HTTPError as e:
        if e.code == 422:
            print("  仓库已存在，复用")
        else:
            raise

def push_files(token, username):
    print("[2/5] 上传项目文件...")
    import glob
    
    files_to_push = []
    for root, dirs, fnames in os.walk(PROJECT_DIR):
        if ".github" in root or "build_apk.py" in fnames:
            continue
        for fname in fnames:
            if fname == "build_apk.py":
                continue
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, PROJECT_DIR).replace("\\", "/")
            files_to_push.append((rel, full))
    
    for idx, (rel, full) in enumerate(files_to_push):
        with open(full, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        
        data = {
            "message": f"Add {rel}",
            "content": content,
        }
        
        try:
            api_request(
                "PUT",
                f"https://api.github.com/repos/{username}/{REPO_NAME}/contents/{rel}",
                token, data
            )
        except urllib.error.HTTPError:
            pass  # file might exist
        
        if idx % 5 == 0:
            print(f"  已上传 {idx+1}/{len(files_to_push)}")
    
    print(f"  完成: {len(files_to_push)} 个文件")

def trigger_workflow(token, username):
    print("[3/5] 触发云端构建...")
    url = f"https://api.github.com/repos/{username}/{REPO_NAME}/actions/workflows/build_apk.yml/dispatches"
    data = {"ref": "main"}
    api_request("POST", url, token, data)
    print("  工作流已触发")

def wait_and_download(token, username):
    print("[4/5] 等待构建完成（预计 8-15 分钟）...")
    
    url = f"https://api.github.com/repos/{username}/{REPO_NAME}/actions/runs"
    
    # Wait for workflow run to appear
    run_id = None
    for _ in range(30):
        time.sleep(10)
        data = json.loads(api_request("GET", url, token))
        runs = data.get("workflow_runs", [])
        if runs:
            run_id = runs[0]["id"]
            print(f"  构建运行 ID: {run_id}")
            break
    
    if not run_id:
        print("  错误：未检测到构建运行")
        return None
    
    # Wait for completion
    run_url = f"https://api.github.com/repos/{username}/{REPO_NAME}/actions/runs/{run_id}"
    dots = 0
    while True:
        time.sleep(30)
        data = json.loads(api_request("GET", run_url, token))
        status = data["status"]
        conclusion = data.get("conclusion")
        
        dots = (dots + 1) % 4
        print(f"  状态: {status} / 结论: {conclusion or '进行中'} {'.' * dots}", end="\r")
        
        if status == "completed":
            print()
            if conclusion == "success":
                print("  构建成功！")
                break
            else:
                print(f"  构建失败 (结论: {conclusion})")
                print(f"  详情: https://github.com/{username}/{REPO_NAME}/actions/runs/{run_id}")
                return None
    
    # Download artifacts
    print("[5/5] 下载 APK...")
    artifacts_url = f"https://api.github.com/repos/{username}/{REPO_NAME}/actions/runs/{run_id}/artifacts"
    data = json.loads(api_request("GET", artifacts_url, token))
    
    for artifact in data.get("artifacts", []):
        if "apk" in artifact["name"].lower():
            download_url = artifact["archive_download_url"]
            print(f"  下载: {artifact['name']} ({artifact['size_in_bytes']} bytes)")
            
            req = urllib.request.Request(download_url)
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("User-Agent", USER_AGENT)
            zip_data = urllib.request.urlopen(req).read()
            
            output_dir = os.path.join(PROJECT_DIR, "output")
            os.makedirs(output_dir, exist_ok=True)
            
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                tmp.write(zip_data)
                tmp_path = tmp.name
            
            import zipfile as zf
            with zf.ZipFile(tmp_path, "r") as z:
                z.extractall(output_dir)
            
            os.unlink(tmp_path)
            
            # Find the APK
            for f in os.listdir(output_dir):
                if f.endswith(".apk"):
                    apk_path = os.path.join(output_dir, f)
                    print(f"\n  APK 已保存到: {apk_path}")
                    return apk_path
    
    print("  未找到 APK 产物")
    return None


def main():
    print("=" * 60)
    print("  乐转站 Android APK 自动构建器")
    print("=" * 60)
    print()
    
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        token = input("请输入 GitHub Token（https://github.com/settings/tokens）: ").strip()
    
    if not token:
        print("需要 GitHub Token 才能继续")
        sys.exit(1)
    
    print(f"项目目录: {PROJECT_DIR}")
    
    try:
        username = get_username(token)
        print(f"GitHub 用户: {username}")
        
        create_repo(token, username)
        push_files(token, username)
        trigger_workflow(token, username)
        apk_path = wait_and_download(token, username)
        
        if apk_path:
            print()
            print("=" * 60)
            print(f"  构建完成！APK 文件: {apk_path}")
            print("=" * 60)
        else:
            print()
            print("构建失败，请检查 GitHub Actions 日志")
            print(f"https://github.com/{username}/{REPO_NAME}/actions")
    
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
（内容由AI生成，仅供参考）
