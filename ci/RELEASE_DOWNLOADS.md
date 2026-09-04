## Downloads

| Platform | Download |
|----------|----------|
| macOS Apple Silicon | `migration-insights-<version>-macos-arm64` |
| Ubuntu amd64 | `migration-insights_<version>-1.ubuntu_amd64.deb` |
| Amazon Linux x86_64 | `migration-insights-<version>-1.amzn.x86_64.rpm` |
| RHEL 8 family | `migration-insights-<version>-1.el8.x86_64.rpm` |
| RHEL 9 family | `migration-insights-<version>-1.el9.x86_64.rpm` |

Release version: `<version>`.

### Quick start

* macOS: `chmod +x migration-insights-<version>-macos-arm64 && ./migration-insights-<version>-macos-arm64`
  * **First run:** If macOS blocks the app, right-click the file → **Open**, or run `xattr -cr ./migration-insights-<version>-macos-arm64` before launching. This is expected for unsigned binaries downloaded from GitHub.
* Ubuntu: `sudo apt install ./migration-insights_<version>-1.ubuntu_amd64.deb`
* Amazon Linux / RHEL: `sudo dnf install ./migration-insights-<version>-1.*.rpm`
* Source: use GitHub’s **Source code (zip)** or **Source code (tar.gz)** on the release page

Full installation, upgrade, and build-from-source instructions are in [PACKAGING.md](https://github.com/mongodb/migration-insights/blob/master/PACKAGING.md).
