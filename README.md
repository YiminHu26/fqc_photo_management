这是用来给FQC做照片归档的仓库

## 设置
1. 将本仓库clone到本地
```bash
git clone https://github.com/YiminHu26/fqc_photo_management.git
```
1. 阅读[教程](https://docs.astral.sh/uv/getting-started/installation/),下载uv,这里我用winget方法
```bash
winget install --id=astral-sh.uv  -e
```

## 使用
1. 把所有图片复制到assets文件夹下，不用重命名，不用分类
1. 确保唛头永远是一台设备所有照片的第一张（最早拍的），这样运行才能成功
1. 在根目录下运行
```
uv run ocr-ws
```