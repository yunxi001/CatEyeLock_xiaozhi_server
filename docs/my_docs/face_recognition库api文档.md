# 安装
## 安装
### 稳定版
要安装 Face Recognition，在终端中运行以下命令：
```
$ pip3 install face_recognition
```
这是安装 Face Recognition 的推荐方法，因为它会始终安装最新的稳定版本。

如果你尚未安装 pip，这份 Python 安装指南可以引导你完成安装流程。

### 从源码安装
Face Recognition 的源码可从 Github 代码仓库下载。

你可以克隆公共代码仓库：
```
$ git clone git://github.com/ageitgey/face_recognition
```
或者下载压缩包：
```
$ curl  -OL https://github.com/ageitgey/face_recognition/tarball/master
```
获取源码副本后，可通过以下命令安装：
```
$ python setup.py install
```


# 使用方法
## 使用方法
要在项目中使用 Face Recognition，需执行以下操作：
```python
import face_recognition
```
可前往 github 上的 `/examples` 文件夹查看各函数的使用示例。
你也可以查阅`face_recognition`模块的 API 文档，了解每个函数可用的参数。

基本使用思路如下：首先加载一张图片：
```python
import face_recognition
image = face_recognition.load_image_file("your_file.jpg")
```
该操作会将图片加载为 numpy 数组。若你已拥有 numpy 数组格式的图片，则可跳过此步骤。

之后你可以对图片执行各类操作，例如检测人脸、识别面部特征或获取人脸编码：
```python
# 检测图片中所有的人脸
face_locations = face_recognition.face_locations(image)
# 也可以识别图片中的面部特征
face_landmarks_list = face_recognition.face_landmarks(image)
# 还能获取图片中每个人脸的编码：
list_of_face_encodings = face_recognition.face_encodings(image)
```

人脸编码可相互比对，以判断人脸是否匹配。注意：生成人脸编码的过程会稍慢，因此如果你后续需要再次查阅这些编码，建议将每张图片的编码结果保存至数据库或缓存中。

获取人脸编码后，你可以按如下方式进行比对：
```python
# results 是一个布尔值数组，用于表示未知人脸是否与 known_faces 数组中的任何人脸匹配
results = face_recognition.compare_faces(known_face_encodings, a_single_unknown_face_encoding)
```


# face_recognition 包
## 模块内容
### `face_recognition.api.batch_face_locations(images, number_of_times_to_upsample=1, batch_size=128)`【源码】
该函数通过CNN人脸检测器返回图像中人脸的二维边界框数组。若你使用GPU，此函数能大幅提升检测速度，因为GPU可同时处理批量图像；若未使用GPU，则无需调用此函数。
- **参数**：
  - images——图像列表（每张图像均为numpy数组格式）
  - number_of_times_to_upsample——对图像进行上采样以查找人脸的次数，数值越大，越容易检测到更小的人脸
  - batch_size——每次GPU处理批次中包含的图像数量
- **返回值**：
  找到的人脸位置元组列表，位置格式遵循CSS（上、右、下、左）顺序

### `face_recognition.api.compare_faces(known_face_encodings, face_encoding_to_check, tolerance=0.6)`【源码】
将一组已知的人脸编码与待检测的人脸编码进行比对，判断二者是否匹配。
- **参数**：
  - known_face_encodings——已知的人脸编码列表
  - face_encoding_to_check——待与列表比对的单个人脸编码
  - tolerance——判定人脸匹配的距离阈值，数值越小匹配判定越严格，0.6为常规最优性能阈值
- **返回值**：
  布尔值列表，用于标识`known_face_encodings`中哪些编码与待检测人脸编码匹配

### `face_recognition.api.face_distance(face_encodings, face_to_compare)`【源码】
给定一组人脸编码，将其与已知人脸编码进行比对，计算每组比对的欧氏距离，距离值可反映人脸的相似程度。
- **参数**：
  - face_encodings——待比对的人脸编码列表
  - face_to_compare——用于比对的基准人脸编码
- **返回值**：
  一个numpy数组，数组中距离值的顺序与传入的`face_encodings`数组顺序一致

### `face_recognition.api.face_encodings(face_image, known_face_locations=None, num_jitters=1, model='small')`【源码】
输入一张图像，返回图像中每张人脸对应的128维人脸编码。
- **参数**：
  - face_image——包含一张或多张人脸的图像
  - known_face_locations——可选参数，若已提前获知人脸边界框，可传入该参数
  - num_jitters——计算人脸编码时对人脸区域的重采样次数，数值越大精度越高，但速度越慢（例如设置为100时，速度会降低100倍）
  - model——可选参数，指定编码模型，可选“large”或“small”（默认值），“small”模型仅返回5个特征点但运算速度更快
- **返回值**：
  128维人脸编码列表（图像中每张人脸对应一个编码）

### `face_recognition.api.face_landmarks(face_image, face_locations=None, model='large')`【源码】
输入一张图像，返回图像中每张人脸的面部特征（眼睛、鼻子等）位置字典。
- **参数**：
  - face_image——待检测的图像
  - face_locations——可选参数，可传入待检测的人脸位置列表
  - model——可选参数，指定特征检测模型，可选“large”（默认值）或“small”，“small”模型仅返回5个特征点但运算速度更快
- **返回值**：
  面部特征位置字典列表（每张人脸对应一个字典，包含眼睛、鼻子等特征的位置信息）

### `face_recognition.api.face_locations(img, number_of_times_to_upsample=1, model='hog')`【源码】
返回图像中人脸的边界框数组。
- **参数**：
  - img——待检测的图像（numpy数组格式）
  - number_of_times_to_upsample——对图像进行上采样以查找人脸的次数，数值越大，越容易检测到更小的人脸
  - model——指定人脸检测模型，可选“hog”或“cnn”。“hog”模型精度较低但在CPU上运算更快；“cnn”为高精度深度学习模型，支持GPU/CUDA加速（若相关环境已配置），默认值为“hog”
- **返回值**：
  找到的人脸位置元组列表，位置格式遵循CSS（上、右、下、左）顺序

### `face_recognition.api.load_image_file(file, mode='RGB')`【源码】
将图像文件（.jpg、.png等格式）加载为numpy数组。
- **参数**：
  - file——待加载的图像文件名或文件对象
  - mode——图像转换格式，仅支持“RGB”（8位RGB，3个通道）和“L”（黑白灰度）两种格式
- **返回值**：
  以numpy数组形式存储的图像内容

