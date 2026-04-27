#!/bin/bash
# git_sync.sh - 一键提交+推送
# 用法: ./git_sync.sh "commit message"
#        ./git_sync.sh          # 打开编辑器写 message

set -euo pipefail
cd "$(dirname "$0")"

msg="${1:-}"

# 检查是否有改动
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo "没有改动，跳过"
    exit 0
fi

# 未提供 message 则用默认或编辑器
if [ -z "$msg" ]; then
    # 生成默认 message
    files=$(git diff --name-only; git diff --cached --name-only; git ls-files --others --exclude-standard)
    count=$(echo "$files" | grep -c . || true)
    preview=$(echo "$files" | head -3 | tr '\n' ' ')
    default="chore: ${count} file(s) changed ($preview)"
    echo "默认提交信息: $default"
    echo -n "确认？(Y/n/输入自定义): "
    read -r confirm
    case "$confirm" in
        n|N) echo "已取消"; exit 0 ;;
        ""|y|Y) msg="$default" ;;
        *) msg="$confirm" ;;
    esac
fi

# Stage all
git add -A

# Commit
if ! git commit -m "$msg"; then
    echo "提交失败"
    exit 1
fi

# Push (retry up to 3 times)
for i in 1 2 3; do
    if git push 2>&1; then
        echo "✓ 推送成功"
        exit 0
    fi
    echo "推送失败，${i}/3 次重试..."
    sleep 3
done

echo "✗ 推送失败，请手动: git push"
exit 1
