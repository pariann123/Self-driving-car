# -*- coding: utf-8 -*-
"""yolo_ML_rules.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1M-j4XESnW1eoVzM09pZ27GM85sECqczt
"""

# Commented out IPython magic to ensure Python compatibility.
from google.colab import drive
drive.mount('/content/drive')
# %cd /content/drive/MyDrive/MSc Computational Neuroscience, Cognition & AI/MLis2/ML Project/code/YOLOv3_TF2/
import sys
from absl import app, logging, flags
from absl.flags import FLAGS
import cv2
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf
import keras

#from yolov3_tf2.models import YoloV3
from yolov3_tf2.yolo import YoloV3
from yolov3_tf2.utils import draw_outputs
class Road:
  def __init__(self, check=False):    
    self.check=check
    self.width, self.height, self.channels = 320, 240, 3
    # object detection YOLO
    #FLAGS.yolo_iou_threshold = 0.05
    #FLAGS.yolo_score_threshold =0.05
    app._run_init(['yolov3'], app.parse_flags_with_usage)
    physical_devices = tf.config.experimental.list_physical_devices('GPU')
    #tf.config.experimental.set_memory_growth(physical_devices[0], True)
    self.yolo = YoloV3(classes=8, yolo_max_boxes=5, yolo_iou_threshold=0.05, yolo_score_threshold=0.05) )
    self.yolo.load_weights('./weights/yolo.tf').expect_partial() 
    # road segmentation UNET
    self.H_unet=128
    self.unet=keras.models.load_model('./weights/unet.h5', custom_objects={'dice_coefficient':0})
    #angle prediction NVIDIA
    self.H_nvidia, self.W_nvidia=88, 128
    self.nvidia=keras.models.load_model('./weights/nvidia.h5')
    self.left=keras.models.load_model('./weights/left.h5')
    self.right=keras.models.load_model('./weights/right.h5')
    # init detection parameters
    self.min_box_area=np.array([1500 ,8000, 520, 1800 ,800 ,520,1800, 800])
    self.class_names=['box','car', 'green light', 'left signal', 'person', 'red light', 'right signal', 'tree']

  def Is_close(self, name, box):
    xmin, ymin, xmax, ymax=box
    area=(xmax-xmin)*(ymax-ymin)*(self.height*self.width)/self.H_unet**2
    class_id=self.class_names.index(name)
    threshold=self.min_box_area[class_id]
    return (area>threshold)

  def Is_obstacle(self,obstacles, road):
    obj=np.zeros_like(road)
    for box in obstacles:
      xmin, ymin, xmax, ymax=box
      obj[ymin:ymax, xmin:xmax]=1
      union=np.sum(np.multiply(road, obj))/((ymax-ymin)*(xmax-xmin))
      if self.check:
        print('union=', union, 'box=', xmin,  xmax, ymin, ymax)
      if union>0.1:
        return True
    return False

  def Angle(self, img, Left, Right):
    img = cv2.resize(img, ( self.H_unet,self.H_unet))
    img=np.reshape(img, (1, self.H_unet, self.H_unet,3))
    lanes=self.unet.predict(img)
    lanes=np.reshape(lanes, (self. H_unet, self.H_unet))
    crop=self.H_unet-self.H_nvidia
    mask =lanes[crop: , :self.W_nvidia]
    mask =np.reshape(mask , (1, self.H_nvidia, self.W_nvidia, 1) )
    if Left or Right:
      if Left:
        angle=self.left.predict(mask)
      if Right:
        angle=self.right.predict(mask)
    else:
      angle=self.nvidia.predict(mask)
    angle=min(float(angle), 1)
    angle=max(float(angle), 0)
    return angle, lanes

  def Is_end_road(self, lanes, angle):
    mask=lanes[:-10, :]
    THR=8
    if angle<0.4:
      S=np.sum(mask[:,:10])
      horizon=np.sum(mask[:40,:])
    if angle>0.6 :
      S=np.sum(mask[:,-10:])
      horizon=np.sum(mask[:40,:])
    if (angle<0.6)*(angle>0.4):
      horizon=np.sum(mask[:64,:])
      S=np.sum(mask[:,self.H_unet//2-5:self.H_unet//2+5])
    end=(S<THR)*(horizon<THR)
    if self.check:
      print( 'End_road:',end, 'S=',S,'horizon=' , horizon)
    return end
    
  def Object(self,img_raw):
    img = tf.expand_dims(img_raw, 0)
    img = tf.image.resize(img, (416, 416))
    img = img/ 255
    boxes, scores, classes, nums = self.yolo(img)     
    new_boxes, new_classes, new_scores=[],[],[]
    for i in range(nums[0]):
      name=self.class_names[int(classes[0][i])]
      new_classes.append(name)
      new_scores.append(np.array(scores[0][i]))
      new_boxes.append(np.array(boxes[0][i]))
    converted_boxes=[]
    for box in new_boxes:
      x1, y1, x2, y2=box 
      xmin=int(x1*self.H_unet)
      xmax=int(x2*self.H_unet)
      ymin=int(y1*self.H_unet)
      ymax=int(y2*self.H_unet)
      xmin, ymax=max(1, xmin), min(self.H_unet-1 , ymax)
      converted_boxes.append([xmin,ymin, xmax, ymax])
    if self.check:
      image = cv2.cvtColor(img_raw, cv2.COLOR_RGB2BGR)
      image= draw_outputs(image, (boxes, scores, classes, nums), self.class_names)
      from IPython.display import Image, display
      display(Image(data=bytes(cv2.imencode('.jpg', image)[1]), width=300))
      print('score=', new_scores, 'classes=', new_classes)
    return converted_boxes,new_classes
 

  def Mask(self, mask, angle, THR=0.2):
    step=8
    M,N=mask.shape[0], mask.shape[1]
    new_mask=np.zeros((M,N))
    x_start=(N//2)*(angle>0.4)*(angle<0.6)+(N//2-30)*(angle<0.4)+(N//2+30)*(angle>0.6)
    first_lane=False
    for y in np.flip(np.arange(0, M-step, step)):
      x1=0; x2=N
      # find left lane
      x=x_start
      while (x>1)*(x1==0):
        if mask[y,x]>THR:
          x1=x
        x-=1
      # find right lane
      x=x_start
      while (x<N-1)*(x2==N):
        if mask[y,x]>THR:
          x2=x
        x+=1
      #update mask
      if  (x1!=0)*(x1!=x2) or (x2!=N)*(x1!=x2):
        first_lane=True
        x_start=(x1+x2)//2
        new_mask[y:y+step, x1:x2]=1
      # if no lanes met: all ones if never met; else end
      else:
        if (y>M//3)*(first_lane==False):
          new_mask[y:y+step, x1:x2]=1
        else:
          return new_mask
    return new_mask


  def Predict(self, img_path):
    speed, Left, Right, obstacles= 1, False, False, []
    img = cv2.imread(img_path)[:,:,:3]
    close, obstacle= False,  False
    boxes, classes =self.Object(img)
    if len(boxes)!=0:
      for box, name in zip(boxes, classes):
        if self.Is_close(name, box):
          close=True
          if name=='red light':
            speed=0
          Left=(name=='left signal')
          Right=(name=='right signal')
          if name=='box' or name=='car' or name=='person' or name=='tree':
            obstacles.append(box)
    angle, lanes= self.Angle(img, Left, Right)
    road=self.Mask(lanes, angle)
    if self.Is_obstacle(obstacles, road):
      speed=0
      obstacle=True
    if self.Is_end_road(lanes, angle):
      speed=0

    if self.check:
      fig, axs=plt.subplots(nrows=1, ncols=2)
      axs[1].imshow(road); axs[0].imshow(lanes>0.2)
      print(' obstacle=', obstacle, ' is_close=', close)
    return speed, angle

"""# Evaluate"""

code_dir='/content/drive/My Drive/MSc Computational Neuroscience, Cognition & AI/MLis2/ML Project/code'

# test images
dataset_dir= os.path.join(code_dir,'data/training_data')
images_dir=os.path.join(dataset_dir, 'training_data')
images_list = os.listdir(images_dir)
print(len(images_list), images_list[:20])
# target values
dataframe = pd.read_csv(code_dir+"/YOLOv3_TF2/data/training_norm.csv")
dataset = np.array(dataframe.values)
SPEED=np.array(dataset[:, 2], dtype=int)
ANGLE=np.array(dataset[:, 1 ], dtype=float)
print(SPEED[:4], ANGLE[:4])

road=Road(check=True)

n=np.random.randint(1,len(images_list))
#n=790
img_path=os.path.join(images_dir,str(n)+'.png')
speed, angle=road.Predict(img_path)
print('prediction: speed=', speed, 'angle=', angle)
print('target: speed=', SPEED[n-1], 'angle=', ANGLE[n-1])

road=Road(check=False)
loss=[]
shit=[]
N=400 #int(len(images_list)/50)
start=800
for i in range(start,start+N):
  img_path=os.path.join(images_dir,str(i)+'.png')
  target_speed, target_angle= SPEED[i-1], ANGLE[i-1]
  speed, angle= road.Predict(img_path)
  l1=speed-target_speed
  l2=angle-target_angle
  if l1!=0 : #or l2!=0:
    shit.append(i)
    print(i, l1)#, l2)
print(len(shit)/N)

"""# Produce exportable csv file"""

code_dir='/content/drive/My Drive/MSc Computational Neuroscience, Cognition & AI/MLis2/ML Project/code'
# test images
dataset_dir= os.path.join(code_dir,'data/test_data')
images_dir=os.path.join(dataset_dir, 'test_data')
images_list = os.listdir(images_dir)
print(len(images_list))

road=Road(check=True)

N=np.random.randint(1,len(images_list))
N=1014
print(N)
#N=1014
img_path=os.path.join(images_dir,str(N)+'.png')
v, angle=road.Predict(img_path)
print('predict=', v, angle)

import time
road=Road(check=False)

t1=time.perf_counter()

N=len(images_list)

pred=[]
i=0
for i in range(N):
  img_id=int(i+1)
  img_name=str(int(img_id))+'.png'
  if i%100==0:
    print(round(i/N*100), '%')
  img_path=os.path.join(images_dir,img_name)
  v, a=road.Predict(img_path)
  pred.append([ int(img_id),  a, int(v)])

t2=time.perf_counter()
print('mean time/prediction=', (t2-t1)/N, 's')

speed_df = pd.DataFrame(np.array(pred), columns=['image_id','angle','speed'])
speed_df[['image_id', 'speed']] = speed_df[['image_id', 'speed']].astype(int)
#check dtype
print(speed_df.dtypes)
# save the dataframe as a csv file
speed_df.to_csv("/content/results_02_05.csv", header=True, index=False)

"""# Produce masks road+boxes"""

code_dir='/content/drive/MyDrive/MSc Computational Neuroscience, Cognition & AI/MLis2/ML Project/code/'
images_dir=code_dir+'/data/training_data/training_data/'
masks_dir=code_dir+'/data/training_data/training_masks/'
new_masks_dir=code_dir+'/data/training_data/masks_road_object/'
images_list=os.listdir(images_dir)
N=len(images_list)

img_width, img_height = 320, 240
scale_x, scale_y=128/320, 128/240

speed=Speed(check=False)

N=len(images_list)
id=int(n-1)
mask_name=str(n)+'.npy'
mask_path=masks_dir+mask_name
new_mask_path=new_masks_dir+mask_name
img_name=str(n)+'.png'
img_path=images_dir+img_name
if os.path.isfile(mask_path):
  mask= np.load(mask_path)
  boxes, classes =speed.Object(img_path)
  if len(boxes)==0:
    a=1
    #np.save(new_mask_path, mask)
  for box, name in zip(boxes, classes):
    if name=='person' or name=='car' or name=='tree' or name=='box':
      xmin,ymin, xmax, ymax=box
      xmin, ymin, xmax, ymax=int(xmin*scale_x), int(ymin*scale_y), int(xmax*scale_x), int(ymax*scale_y)
      mask[ymin:ymax, xmin:xmax]=1
      #np.save(new_mask_path, mask)

fig, axs=plt.subplots(1,2)  
axs[1].imshow(mask)
img = imread(img_path)[:,:,:3]
axs[0].imshow(img)

N=len(images_list)
for i in range(10, N):
  if i%500==0:
    print(i/N, '%')
  
  mask_name=str(i)+'.npy'
  mask_path=masks_dir+mask_name
  new_mask_path=new_masks_dir+mask_name
  img_name=str(i)+'.png'
  img_path=images_dir+img_name
  if os.path.isfile(mask_path):
    mask= np.load(mask_path)
    boxes, classes =speed.Object(img_path)
    if len(boxes)==0:
      np.save(new_mask_path, mask)
    for box, name in zip(boxes, classes):
      if name=='person' or name=='car' or name=='tree' or name=='box':
        xmin,ymin, xmax, ymax=box
        xmin, ymin, xmax, ymax=int(xmin*scale_x), int(ymin*scale_y), int(xmax*scale_x), int(ymax*scale_y)
        mask[ymin:ymax, xmin:xmax]=1
        np.save(new_mask_path, mask)

"""# Draft"""

def dice_coefficient(y_true, y_pred):
  numerator = 2 * tf.reduce_sum(y_true * y_pred)
  denominator = tf.reduce_sum(y_true + y_pred)
  return numerator / (denominator + tf.keras.backend.epsilon())

results_df=pd.read_csv('/content/results_02_05.csv', delimiter=',')
results_array=results_df.to_numpy()
print(results_array[:5,:])



speed_df = pd.DataFrame(np.array(results_array), columns=['image_id','angle','speed'])
speed_df[['image_id', 'speed']] = speed_df[['image_id', 'speed']].astype(int)
#check dtype
print(speed_df.dtypes)
# save the dataframe as a csv file
speed_df.to_csv("/content/result_02_05.csv", header=True, index=False)

import time

speed=Speed(check=False)

t1=time.perf_counter()
N=len(images_list)
pred=[]
i=0
for img_id,angle,_ in results_array:
  i+=1
  img_name=str(int(img_id))+'.png'
  if i%100==0:
    print(round(i/N*100), '%')
  img_path=os.path.join(images_dir,img_name)
  v, a=speed.Give_speed(img_path)
  if a!=None:
    angle=a
  pred.append([ int(img_id),  max(angle,0), int(v)])

t2=time.perf_counter()
print('execution time', (t2-t1)/N)

speed_df = pd.DataFrame(np.array(pred), columns=['image_id','angle','speed'])
speed_df[['image_id', 'speed']] = speed_df[['image_id', 'speed']].astype(int)
#check dtype
print(speed_df.dtypes)
# save the dataframe as a csv file
speed_df.to_csv("results_29_04.csv", header=True, index=False)

def Is_obstacle(self,name, box, mask):
    if name=='left signal' or name=='right signal' or name=='green light' or name=='red light':
      return False
    xmin, ymin, xmax, ymax=box
    if  (xmax-xmin)*(ymax-ymin)>self.super_close_box : # or ymax>=self.height-10
      return True
    N, THR=128, 0.5
    xmin,  xmax, ymin, ymax=int(xmin*N/self.width),  int(xmax*N/self.width), int(ymin*N/self.height), int(ymax*N/self.height)
    x_c, y_c=int(xmin+0.5*(xmax-xmin)), int(ymin+0.5*(ymax-ymin))
    xmax, ymax=min(xmax, N-1), min(ymax,N-1)
    crossed_lines_down, crossed_lines_up =0,0
    for x in [xmin,x_c, xmax]:
      y=ymax
      down=0
      while (y<N-1)*(down==0):
          y+=1
          if mask[y,x]>THR:
            down=1
      crossed_lines_down+=down
      y=ymax
      up=0
      while (y>y_c)*(up==0):
          y-=1
          if mask[y,x]>THR:
            up=1
      crossed_lines_up+=up

max_union=(xmax-xmin)*(y2-y1)
      obj=np.zeros((N,))
      obj[xmin:xmax]=1
      for y in range(y1,y2):
        road=np.zeros((N,))
        x1, x2 =-1,-1
        x=0
        while (x<N-1)*(x1<0)*(mask[y,x]<THR):
          x+=1
        x1=x
        # find middle line
        x=min(x1+10, N-1)
        while (x<N-1)*(x2<0)*(mask[y,x]<THR):
          x+=1
        x2=x
        road[x1:x2]=1
        union+=np.inner(road, obj )
      if union>0.3*max_union:
        return True
      else:
        return False

if down<THR:
      if (left>THR)*(right>THR) or (left>THR)*(up>THR) or (left<THR)*(right>THR)*(up>THR) or (left>THR)*(right<THR)*(up<THR):
        return True 
      else:
        return False
    else: #if down>THR:
      if (left>THR)*(right>THR)*(up>THR) or (left>THR)*(up>THR) or inside>THR:
        return True
      else:
        return False

def Is_obstacle(self,name, box, mask):
    if name=='left signal' or name=='right signal' or name=='green light' or name=='red light':
      return False
    xmin, ymin, xmax, ymax=box
    N, THR=128, 1
    xmin,  xmax, ymin, ymax=int(xmin*N/self.width),  int(xmax*N/self.width), int(ymin*N/self.height), int(ymax*N/self.height)
    x_c, y_c=int(xmin+0.5*(xmax-xmin)), int(ymin+0.5*(ymax-ymin))
    xmax, ymax=min(xmax, N-1), min(ymax,N-1)
    xmin, ymin= max(1, xmin), max(1,ymin)
    if (x_c>N//2-20)*(x_c<N//2+20)*(ymax>N-20):
      return True
    down= np.sum(mask[ymax:max(ymax, N-5) ,x_c])
    up= np.sum(mask[:ymax, xmin:xmax])/(xmax-xmin)
    left=np.sum(mask[ymax-10:ymax, :xmin])/10
    right= np.sum(mask[ymax-10:ymax, xmax:])/10
    inside=np.sum(mask[ymin+10:ymax, xmin+10:xmax])/((xmax-xmin)+(ymax-ymin))
    if self.check:
      print('D',down,'u',up, 'L',left, 'R',right, 'inside', inside)
    if (down>THR)*(left>THR)*(up>THR):
      return True
    if down<THR:
      if inside>0.5 or (left>THR) or (right>THR)*(up>THR) or up>THR:
        return True
      else:
        return False
    else:
      return False

"""# YOLO transform"""

import numpy as np
import tensorflow as tf
from tensorflow.keras import Model
from tensorflow.keras.layers import (
    Add,
    Concatenate,
    Conv2D,
    Input,
    Lambda,
    LeakyReLU,
    MaxPool2D,
    UpSampling2D,
    ZeroPadding2D,
    BatchNormalization,
)
from tensorflow.keras.regularizers import l2
from tensorflow.keras.losses import (
    binary_crossentropy,
    sparse_categorical_crossentropy
)



yolo_anchors = np.array([(10, 13), (16, 30), (33, 23), (30, 61), (62, 45),
                         (59, 119), (116, 90), (156, 198), (373, 326)],
                        np.float32) / 416
yolo_anchor_masks = np.array([[6, 7, 8], [3, 4, 5], [0, 1, 2]])


def DarknetConv(x, filters, size, strides=1, batch_norm=True):
    if strides == 1:
        padding = 'same'
    else:
        x = ZeroPadding2D(((1, 0), (1, 0)))(x)  # top left half-padding
        padding = 'valid'
    x = Conv2D(filters=filters, kernel_size=size,
               strides=strides, padding=padding,
               use_bias=not batch_norm, kernel_regularizer=l2(0.0005))(x)
    if batch_norm:
        x = BatchNormalization()(x)
        x = LeakyReLU(alpha=0.1)(x)
    return x


def DarknetResidual(x, filters):
    prev = x
    x = DarknetConv(x, filters // 2, 1)
    x = DarknetConv(x, filters, 3)
    x = Add()([prev, x])
    return x


def DarknetBlock(x, filters, blocks):
    x = DarknetConv(x, filters, 3, strides=2)
    for _ in range(blocks):
        x = DarknetResidual(x, filters)
    return x


def Darknet(name=None):
    x = inputs = Input([None, None, 3])
    x = DarknetConv(x, 32, 3)
    x = DarknetBlock(x, 64, 1)
    x = DarknetBlock(x, 128, 2)  # skip connection
    x = x_36 = DarknetBlock(x, 256, 8)  # skip connection
    x = x_61 = DarknetBlock(x, 512, 8)
    x = DarknetBlock(x, 1024, 4)
    return tf.keras.Model(inputs, (x_36, x_61, x), name=name)


def DarknetTiny(name=None):
    x = inputs = Input([None, None, 3])
    x = DarknetConv(x, 16, 3)
    x = MaxPool2D(2, 2, 'same')(x)
    x = DarknetConv(x, 32, 3)
    x = MaxPool2D(2, 2, 'same')(x)
    x = DarknetConv(x, 64, 3)
    x = MaxPool2D(2, 2, 'same')(x)
    x = DarknetConv(x, 128, 3)
    x = MaxPool2D(2, 2, 'same')(x)
    x = x_8 = DarknetConv(x, 256, 3)  # skip connection
    x = MaxPool2D(2, 2, 'same')(x)
    x = DarknetConv(x, 512, 3)
    x = MaxPool2D(2, 1, 'same')(x)
    x = DarknetConv(x, 1024, 3)
    return tf.keras.Model(inputs, (x_8, x), name=name)


def YoloConv(filters, name=None):
    def yolo_conv(x_in):
        if isinstance(x_in, tuple):
            inputs = Input(x_in[0].shape[1:]), Input(x_in[1].shape[1:])
            x, x_skip = inputs

            # concat with skip connection
            x = DarknetConv(x, filters, 1)
            x = UpSampling2D(2)(x)
            x = Concatenate()([x, x_skip])
        else:
            x = inputs = Input(x_in.shape[1:])

        x = DarknetConv(x, filters, 1)
        x = DarknetConv(x, filters * 2, 3)
        x = DarknetConv(x, filters, 1)
        x = DarknetConv(x, filters * 2, 3)
        x = DarknetConv(x, filters, 1)
        return Model(inputs, x, name=name)(x_in)
    return yolo_conv





def YoloOutput(filters, anchors, classes, name=None):
    def yolo_output(x_in):
        x = inputs = Input(x_in.shape[1:])
        x = DarknetConv(x, filters * 2, 3)
        x = DarknetConv(x, anchors * (classes + 5), 1, batch_norm=False)
        x = Lambda(lambda x: tf.reshape(x, (-1, tf.shape(x)[1], tf.shape(x)[2],
                                            anchors, classes + 5)))(x)
        return tf.keras.Model(inputs, x, name=name)(x_in)
    return yolo_output


# As tensorflow lite doesn't support tf.size used in tf.meshgrid, 
# we reimplemented a simple meshgrid function that use basic tf function.
def _meshgrid(n_a, n_b):

    return [
        tf.reshape(tf.tile(tf.range(n_a), [n_b]), (n_b, n_a)),
        tf.reshape(tf.repeat(tf.range(n_b), n_a), (n_b, n_a))
    ]


def yolo_boxes(pred, anchors, classes):
    # pred: (batch_size, grid, grid, anchors, (x, y, w, h, obj, ...classes))
    grid_size = tf.shape(pred)[1:3]
    box_xy, box_wh, objectness, class_probs = tf.split(
        pred, (2, 2, 1, classes), axis=-1)

    box_xy = tf.sigmoid(box_xy)
    objectness = tf.sigmoid(objectness)
    class_probs = tf.sigmoid(class_probs)
    pred_box = tf.concat((box_xy, box_wh), axis=-1)  # original xywh for loss

    # !!! grid[x][y] == (y, x)
    grid = _meshgrid(grid_size[1],grid_size[0])
    grid = tf.expand_dims(tf.stack(grid, axis=-1), axis=2)  # [gx, gy, 1, 2]

    box_xy = (box_xy + tf.cast(grid, tf.float32)) / \
        tf.cast(grid_size, tf.float32)
    box_wh = tf.exp(box_wh) * anchors

    box_x1y1 = box_xy - box_wh / 2
    box_x2y2 = box_xy + box_wh / 2
    bbox = tf.concat([box_x1y1, box_x2y2], axis=-1)

    return bbox, objectness, class_probs, pred_box


def yolo_nms(outputs, anchors, masks, classes, yolo_max_boxes, yolo_iou_threshold, yolo_score_threshold):
    # boxes, conf, type
    b, c, t = [], [], []

    for o in outputs:
        b.append(tf.reshape(o[0], (tf.shape(o[0])[0], -1, tf.shape(o[0])[-1])))
        c.append(tf.reshape(o[1], (tf.shape(o[1])[0], -1, tf.shape(o[1])[-1])))
        t.append(tf.reshape(o[2], (tf.shape(o[2])[0], -1, tf.shape(o[2])[-1])))

    bbox = tf.concat(b, axis=1)
    confidence = tf.concat(c, axis=1)
    class_probs = tf.concat(t, axis=1)

    scores = confidence * class_probs

    dscores = tf.squeeze(scores, axis=0)
    scores = tf.reduce_max(dscores,[1])
    bbox = tf.reshape(bbox,(-1,4))
    classes = tf.argmax(dscores,1)
    selected_indices, selected_scores = tf.image.non_max_suppression_with_scores(
        boxes=bbox,
        scores=scores,
        max_output_size=yolo_max_boxes,
        iou_threshold=yolo_iou_threshold,
        score_threshold=yolo_score_threshold,
        soft_nms_sigma=0.5
    )
    
    num_valid_nms_boxes = tf.shape(selected_indices)[0]

    selected_indices = tf.concat([selected_indices,tf.zeros(yolo_max_boxes-num_valid_nms_boxes, tf.int32)], 0)
    selected_scores = tf.concat([selected_scores,tf.zeros(yolo_max_boxes-num_valid_nms_boxes,tf.float32)], -1)

    boxes=tf.gather(bbox, selected_indices)
    boxes = tf.expand_dims(boxes, axis=0)
    scores=selected_scores
    scores = tf.expand_dims(scores, axis=0)
    classes = tf.gather(classes,selected_indices)
    classes = tf.expand_dims(classes, axis=0)
    valid_detections=num_valid_nms_boxes
    valid_detections = tf.expand_dims(valid_detections, axis=0)

    return boxes, scores, classes, valid_detections


def YoloV3(size=None, channels=3, anchors=yolo_anchors,
           masks=yolo_anchor_masks, classes=8, yolo_max_boxes=5, yolo_iou_threshold=0.05, yolo_score_threshold=0.05):
    x = inputs = Input([size, size, channels], name='input')

    x_36, x_61, x = Darknet(name='yolo_darknet')(x)

    x = YoloConv(512, name='yolo_conv_0')(x)
    output_0 = YoloOutput(512, len(masks[0]), classes, name='yolo_output_0')(x)

    x = YoloConv(256, name='yolo_conv_1')((x, x_61))
    output_1 = YoloOutput(256, len(masks[1]), classes, name='yolo_output_1')(x)

    x = YoloConv(128, name='yolo_conv_2')((x, x_36))
    output_2 = YoloOutput(128, len(masks[2]), classes, name='yolo_output_2')(x)

    boxes_0 = Lambda(lambda x: yolo_boxes(x, anchors[0], classes),
                     name='yolo_boxes_0')(output_0)
    boxes_1 = Lambda(lambda x: yolo_boxes(x, anchors[1], classes),
                     name='yolo_boxes_1')(output_1)
    boxes_2 = Lambda(lambda x: yolo_boxes(x, anchors[2], classes),
                     name='yolo_boxes_2')(output_2)

    outputs = Lambda(lambda x: yolo_nms(x, anchors, masks, classes, yolo_max_boxes, yolo_iou_threshold, yolo_score_threshold),
                     name='yolo_nms')((boxes_0[:3], boxes_1[:3], boxes_2[:3]))

    model=Model(inputs, outputs, name='yolov3')
    model.compile()
    return model

model = YoloV3()

model.load_weights('./weights/yolo.tf').expect_partial()

N=np.random.randint(1,len(images_list))
print(N)
#N=1014
img_path=os.path.join(images_dir,str(N)+'.png')
img=cv2.imread(img_path)[:,:,:3]

img = tf.expand_dims(img, 0)
img = tf.image.resize(img, (416, 416))
img = img/ 255
boxes, scores, classes, nums = model(img)   
print(boxes, scores, classes)

model.save('/content/yolo.h5')

model=keras.models.load_model('/content/yolo.h5')

N=np.random.randint(1,len(images_list))
print(N)
#N=1014
img_path=os.path.join(images_dir,str(N)+'.png')
img=cv2.imread(img_path)[:,:,:3]
img = tf.expand_dims(img, 0)
img = tf.image.resize(img, (416, 416))
img = img/ 255
boxes, scores, classes, nums = model(img)   
print(boxes, scores, classes)

model.save('./weights/yolov3.h5')