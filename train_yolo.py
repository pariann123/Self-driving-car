# -*- coding: utf-8 -*-
"""train_yolo.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1X4yOPoWdGXJUBQgKaYbpXIuUXFAAFZmI

# YoloV3 TF2 GPU Colab Notebook

##### 1.  Clone and install dependencies 

**IMPORTANT**: Restart following the instruction
"""

!nvidia-smi

# Commented out IPython magic to ensure Python compatibility.
!git clone https://github.com/zzh8829/yolov3-tf2
# %cd /content/yolov3-tf2/
!pip install -r requirements-gpu.txt

"""##### 2.  Check Tensorflow2 version"""

# Commented out IPython magic to ensure Python compatibility.
# %cd /content/yolov3-tf2/
!ls

import tensorflow as tf
tf.__version__

"""##### 3.  Convert Pretrained Darknet Weight"""

!wget https://pjreddie.com/media/files/yolov3.weights -O data/yolov3.weights

# Commented out IPython magic to ensure Python compatibility.
# %cd /content/yolov3-tf2
!python convert.py --weights ./data/yolov3.weights --output ./data/yolov3.tf

"""##### 4. Initialize Detector"""

import sys
from absl import app, logging, flags
from absl.flags import FLAGS
import time
import cv2
import numpy as np
import tensorflow as tf
from yolov3_tf2.models import (YoloV3, YoloV3Tiny)
from yolov3_tf2.dataset import transform_images, load_tfrecord_dataset
from yolov3_tf2.utils import draw_outputs

flags.DEFINE_string('classes', './data/coco.names', 'path to classes file')
flags.DEFINE_string('weights', './data/yolov3.tf',
                    'path to weights file')
flags.DEFINE_boolean('tiny', False, 'yolov3 or yolov3-tiny')
flags.DEFINE_integer('size', 416, 'resize images to')
flags.DEFINE_string('image', './data/girl.png', 'path to input image')
flags.DEFINE_string('tfrecord', None, 'tfrecord instead of image')
flags.DEFINE_string('output', './output.jpg', 'path to output image')
flags.DEFINE_integer('num_classes', 80, 'number of classes in the model')

app._run_init(['yolov3'], app.parse_flags_with_usage)

physical_devices = tf.config.experimental.list_physical_devices('GPU')
tf.config.experimental.set_memory_growth(physical_devices[0], True)

"""##### 4. Detect Image"""

FLAGS.image = 'data/meme.jpg'

if FLAGS.tiny:
    yolo = YoloV3Tiny(classes=FLAGS.num_classes)
else:
    yolo = YoloV3(classes=FLAGS.num_classes)
      
yolo.load_weights(FLAGS.weights).expect_partial()
logging.info('weights loaded')

class_names = [c.strip() for c in open(FLAGS.classes).readlines()]
logging.info('classes loaded')

img_raw = tf.image.decode_image(
    open(FLAGS.image, 'rb').read(), channels=3)

img = tf.expand_dims(img_raw, 0)
img = transform_images(img, FLAGS.size)

t1 = time.time()
boxes, scores, classes, nums = yolo(img)
t2 = time.time()
logging.info('time: {}'.format(t2 - t1))

logging.info('detections:')
for i in range(nums[0]):
    logging.info('\t{}, {}, {}'.format(class_names[int(classes[0][i])],
                                        np.array(scores[0][i]),
                                        np.array(boxes[0][i])))

img = cv2.cvtColor(img_raw.numpy(), cv2.COLOR_RGB2BGR)
img = draw_outputs(img, (boxes, scores, classes, nums), class_names)

from IPython.display import Image, display
display(Image(data=bytes(cv2.imencode('.jpg', img)[1]), width=800))

"""##### 5. Training New Dataset"""

!wget http://host.robots.ox.ac.uk/pascal/VOC/voc2009/VOCtrainval_11-May-2009.tar -O ./data/voc2009_raw.tar
!mkdir -p ./data/voc2009_raw
!tar -xf ./data/voc2009_raw.tar -C ./data/voc2009_raw

!python tools/voc2012.py \
  --data_dir './data/voc2009_raw/VOCdevkit/VOC2009' \
  --split train \
  --output_file ./data/voc_train.tfrecord

!python tools/voc2012.py \
  --data_dir './data/voc2009_raw/VOCdevkit/VOC2009' \
  --split val \
  --output_file ./data/voc_val.tfrecord

!python tools/visualize_dataset.py --dataset ./data/voc_train.tfrecord --classes=./data/voc2012.names

from IPython.display import Image
Image(filename='./output.jpg')

!python train.py \
	--dataset ./data/voc_train.tfrecord \
	--val_dataset ./data/voc_val.tfrecord \
	--classes ./data/voc2012.names \
	--num_classes 20 \
	--mode fit --transfer darknet \
	--batch_size 16 \
	--epochs 3 \
	--weights ./checkpoints/yolov3.tf \
	--weights_num_classes 80

import numpy as np
from yolov3_tf2.models import YoloV3
import tensorflow as tf

yolo = YoloV3(classes=8)
#yolo.summary()
yolo.load_weights('./checkpoints/yolov3_train_3.tf')
yolo.save_weights('./data/yolov3_train_3.tf')

"""##### 6. Detect using new weights"""

FLAGS.num_classes = 20
FLAGS.classes = 'data/voc2012.names'
FLAGS.weights = 'checkpoints/yolov3_train_3.tf'
FLAGS.image = 'data/meme.jpg'

# Lower threshold due to insufficient training
FLAGS.yolo_iou_threshold = 0.2
FLAGS.yolo_score_threshold = 0.2

if FLAGS.tiny:
    yolo = YoloV3Tiny(classes=FLAGS.num_classes)
else:
    yolo = YoloV3(classes=FLAGS.num_classes)

yolo.load_weights(FLAGS.weights).expect_partial()
logging.info('weights loaded')

class_names = [c.strip() for c in open(FLAGS.classes).readlines()]
logging.info('classes loaded')

img_raw = tf.image.decode_image(open(FLAGS.image, 'rb').read(), channels=3)

img = tf.expand_dims(img_raw, 0)
img = transform_images(img, FLAGS.size)

t1 = time.time()
boxes, scores, classes, nums = yolo(img)
t2 = time.time()
logging.info('time: {}'.format(t2 - t1))

logging.info('detections:')
for i in range(nums[0]):
    logging.info('\t{}, {}, {}'.format(class_names[int(classes[0][i])],
                                        np.array(scores[0][i]),
                                        np.array(boxes[0][i])))

img = cv2.cvtColor(img_raw.numpy(), cv2.COLOR_RGB2BGR)
img = draw_outputs(img, (boxes, scores, classes, nums), class_names)

from IPython.display import Image, display
display(Image(data=bytes(cv2.imencode('.jpg', img)[1]), width=800))

"""# 7. My training

inspired from https://machinelearningspace.com/yolov3-tensorflow-2-part-3/
"""

import numpy as np
import cv2
import time
import os
import matplotlib.pyplot as plt
import pandas as pd
# keras
import tensorflow as tf
from tensorflow.keras import Model
from tensorflow.keras.layers import BatchNormalization, Conv2D, Input, ZeroPadding2D, LeakyReLU, UpSampling2D

import xml.etree.ElementTree as ET

from google.colab import drive
drive.mount('/content/drive')

code_dir='/content/drive/My Drive/MSc Computational Neuroscience, Cognition & AI/MLis2/ML Project/code'

# test images
dataset_dir= os.path.join(code_dir,'data/test_data')
images_dir=os.path.join(dataset_dir, 'test_data')
images_list = os.listdir(images_dir)
print(images_list[:20])

"""### Data preprocessing

upload traffic_train.tfrecord, traffic_val.tfrecord, traffic.names
"""

import sys
from absl import app, logging, flags
from absl.flags import FLAGS
import time
import cv2
import numpy as np
import tensorflow as tf
from yolov3_tf2.models import YoloV3
from yolov3_tf2.dataset import transform_images, load_tfrecord_dataset
from yolov3_tf2.utils import draw_outputs

flags.DEFINE_string('classes', './data/traffic.names', 'path to classes file')
flags.DEFINE_string('weights', './data/yolov3.tf',
                    'path to weights file')
flags.DEFINE_boolean('tiny', False, 'yolov3 or yolov3-tiny')
flags.DEFINE_integer('size', 416, 'resize images to')
flags.DEFINE_string('image', './data/girl.png', 'path to input image')
flags.DEFINE_string('tfrecord', None, 'tfrecord instead of image')
flags.DEFINE_string('output', './output.jpg', 'path to output image')
flags.DEFINE_integer('num_classes', 8, 'number of classes in the model')

app._run_init(['yolov3'], app.parse_flags_with_usage)

physical_devices = tf.config.experimental.list_physical_devices('GPU')
tf.config.experimental.set_memory_growth(physical_devices[0], True)

"""### train

import traffic_train.tfrecord, traffic_val.tfrecord, traffic.names (txt file names by order of class)
"""

!python tools/visualize_dataset.py --dataset ./data/traffic_train.tfrecord --classes=./data/traffic.names

"""  --mode eager_tf --transfer fine_tune \

"""

!python train.py \
	--dataset ./data/traffic_train.tfrecord \
	--val_dataset ./data/traffic_val.tfrecord \
	--classes ./data/traffic.names \
	--num_classes 8 \
	--mode fit --transfer darknet \
	--batch_size 16 \
	--epochs 30\
	--weights ./data/yolov3.tf \
	--weights_num_classes 80

"""try on image"""

FLAGS.num_classes = 8
FLAGS.classes = 'data/traffic.names'
FLAGS.weights = 'checkpoints/yolov3_train_18.tf'


# Lower threshold due to insufficient training
FLAGS.yolo_iou_threshold = 0.02
FLAGS.yolo_score_threshold = 0.02

yolo = YoloV3(classes=FLAGS.num_classes)

yolo.load_weights(FLAGS.weights).expect_partial()
logging.info('weights loaded')
#yolo.save_weights('/content/drive/My Drive/MSc Computational Neuroscience, Cognition & AI/MLis2/ML Project/code/yolov3_train_18.tf')
#logging.info('weights saved in ./data/')

class_names = [c.strip() for c in open(FLAGS.classes).readlines()]
logging.info('classes loaded')

N=np.random.randint(len(images_list))
#N=10
print(N)
FLAGS.image = os.path.join(images_dir, str(N)+'.png')
img_raw = tf.image.decode_image(open(FLAGS.image, 'rb').read(), channels=3)
img = tf.expand_dims(img_raw, 0)
img = transform_images(img, FLAGS.size)
t1 = time.time()
boxes, scores, classes, nums = yolo(img)
t2 = time.time()
logging.info('time: {}'.format(t2 - t1))

logging.info('detections:')
for i in range(nums[0]):
    logging.info('\t{}, {}, {}'.format(class_names[int(classes[0][i])],np.array(scores[0][i]), np.array(boxes[0][i])))

img = cv2.cvtColor(img_raw.numpy(), cv2.COLOR_RGB2BGR)
img = draw_outputs(img, (boxes, scores, classes, nums), class_names)

from IPython.display import Image, display
display(Image(data=bytes(cv2.imencode('.jpg', img)[1]), width=400))

"""# Draft """



from sklearn.model_selection import train_test_split
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)
tf.random.set_seed(RANDOM_SEED)
train_annots, test_annots = train_test_split(annots_list, test_size=0.1, random_state=RANDOM_SEED)

"""create a file classes.txt with classes by order of id and save in YOLOv3/data"""

name_classes=[['person'],['red light'], ['green light'],['left signal'],['right signal'],['tree'],['box'],['car']]

classes=pd.DataFrame(name_classes)
print(classes.head())

print('class id for red light=', name_classes.index(['red light']))

path=os.path.join('./data/classes.txt')
classes.to_csv(path, header=None, index=None)
!head ./data/classes.txt

"""Create two files inside the data folder, train.txt, and test.txt"""

def extract_xml(filepath):
  tree = ET.parse(filepath)
  root = tree.getroot()
  # extract image dimensions
  width = int(root.find('.//size/width').text) 
  height = int(root.find('.//size/height').text)
  xmins,xmaxs,ymins,ymaxs, names, ids=[], [], [], [], [], []
  for obj in root.findall('.//object'):
    box=obj.find('bndbox')
    xmin = int(box.find('xmin').text)/width #normalized coordinates
    xmax = int(box.find('xmax').text)/width
    ymin = int(box.find('ymin').text)/height
    ymax = int(box.find('ymax').text)/height
    name = obj.find('.//name').text
    class_id=name_classes.index([str(name)])
    xmins.append(xmin);xmaxs.append(xmax);ymins.append(ymin);ymaxs.append(ymax)
    names.append(name)
    ids.append(class_id)
  return  width, height, names, ids, xmins,xmaxs,ymins,ymaxs
  
filepath=os.path.join(annots_dir,annots_list[0])
print(annots_list[0])
print(extract_xml(filepath))

"""create Yolo annotations img_id.txt for each image. Save into YOLOv3_TF2/data

change and upload my data as: train.tfrecord, test.tfrecord, traffic.names and put them in ./data

conversion in tf.record
"""

'''
sys.path.append("..")
from object_detection.utils import ops as utils_ops
from object_detection.utils import dataset_util
'''

flags = tf.app.flags
flags.DEFINE_string('output_path', '', 'Path to output TFRecord')
FLAGS = flags.FLAGS


def create_tf_example(example):
  [height, width, img_path, xmins, xmaxs, ymins, ymaxs, classes_text, classes]=example
  # TODO(user): Populate the following variables from your example.
  filename = img_path # Filename of the image. Empty if image is not from file
  encoded_image_data = None # Encoded image bytes
  image_format = 'png'

  #xmins = List of normalized left x coordinates in bounding box (1 per box)
  #xmaxs = List of normalized right x coordinates in bounding box (1 per box)
  #ymins= List of normalized top y coordinates in bounding box (1 per box)
  #ymaxs= List of normalized bottom y coordinates in bounding box (1 per box)
  #classes_text= List of string class name of bounding box (1 per box)
  #classes= List of integer class id of bounding box (1 per box)
  tf_example = tf.train.Example(features=tf.train.Features(feature={
      'image/height': height,
      'image/width': width,
      'image/filename': filename,
      'image/source_id': filename,
      'image/encoded': encoded_image_data,
      'image/format': image_format,
      'image/object/bbox/xmin': xmins,
      'image/object/bbox/xmax': xmaxs,
      'image/object/bbox/ymin': ymins,
      'image/object/bbox/ymax': ymaxs,
      'image/object/class/text': classes_text,
      'image/object/class/label': classes }))
  return tf_example

def xlm_to_tf(annots_list):
  writer = tf.python_io.TFRecordWriter(FLAGS.output_path)
  for annot_name in annots_list:
    img_id=annot_name[:-4]
    img_name=img_id+'.png'
    img_path = os.path.join( images_dir, img_name)
    annot_path=os.path.join( annots_dir, annot_name)
    width, height, names, ids, xmins,xmaxs,ymins,ymaxs= extract_xml(annot_path)
    example=[height,width,img_path,xmins,xmaxs,ymins,ymaxs,names, ids]
    tf_example = create_tf_example(example)
    writer.write(tf_example.SerializeToString())
  writer.close()

train.tfrecord=xlm_to_tf(train_annots)

test.tfrecord=xlm_to_tf(test_annots)