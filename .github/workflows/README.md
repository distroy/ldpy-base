# PyPI 自动发布说明

工作流文件：[`publish.yml`](./publish.yml)

## 触发方式

代码合并（push）到 `master` 分支后自动触发。流程：

1. 读取 [`pyproject.toml`](../../pyproject.toml) 中的 `version`。
2. 校验版本格式（见下）。
3. 若对应 tag **不存在**，则自动创建带注释的 tag 并推送到 GitHub。
4. 构建并发布到 PyPI。
5. 在该 tag 上创建 **GitHub Release**，并把构建产物（`.whl` 和 sdist `.tar.gz`）作为可下载附件上传。
6. 若 tag **已存在**，则跳过打 tag、发布与建 Release（幂等，避免重复发布同一版本）。

## 产物下载

- **Tags 页面**：GitHub 对任何 tag 自动提供 `Source code (zip / tar.gz)`（源码，无需配置）。
- **Releases 页面**：本工作流会额外把 `.whl` 和 sdist `.tar.gz` 作为 assets 挂到对应 Release 下，可直接下载 —— 与常见 pip 包在 Release 下能下载 wheel 的效果一致。
- **PyPI**：`pip install ldpy.base` 正常安装。

## 版本格式（只允许两种）

| 格式 | 示例 | git tag | 上传到 PyPI 的版本 |
| --- | --- | --- | --- |
| 纯版本号 | `0.0.4` | `0.0.4` | `0.0.4` |
| post release | `0.0.4.post1` | `0.0.4.post1` | `0.0.4.post1` |

其他任何格式（如 `0.0.4.dev5`、`v0.0.4`、`0.0.4+fix1`）都会导致工作流校验失败并终止。

> **为什么用 `.postN` 而不是 `+fixN`？**
> PEP 440 中 `+fixN` 属于「本地版本标识符（local version）」，PyPI 明确拒绝上传（返回 HTTP 400）。
> 而 `.postN` 是合法的 post-release 版本，PyPI 直接接受。
> 因此无需任何改写 —— git tag、GitHub Release、PyPI 三处版本号完全一致。

## 一次性配置（必须）

工作流使用 **PyPI Trusted Publishing（OIDC）**，无需在仓库中存放 API Token。需在 PyPI 侧完成一次性配置：

1. 登录 <https://pypi.org>，进入项目 `ldpy.base` → **Publishing** → **Add a new pending publisher**（首次发布前用 pending publisher）。
2. 填写：
   - **Owner**：`distroy`
   - **Repository name**：`ldpy-base`
   - **Workflow name**：`publish.yml`
   - **Environment name**：`pypi`
3. 在 GitHub 仓库 **Settings → Environments** 中创建名为 `pypi` 的 environment（可选加保护规则/审批）。

配置完成后，合并到 `master` 即可自动发布。

## 如果想用 API Token 而非 Trusted Publishing

将 `publish.yml` 最后一步替换为：

```yaml
      - name: Publish to PyPI
        if: steps.tagcheck.outputs.exists == 'false'
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
```

并在仓库 **Settings → Secrets and variables → Actions** 中添加 `PYPI_API_TOKEN`。此时可删除 job 中的 `environment: pypi`（除非你仍想用 environment 管理 secret）。
