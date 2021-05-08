# -*- coding: utf-8 -*-
"""Run_autopilot.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1UGcjuM53hy6va6CfiiPY3yHpnXkgX4Lo
"""

from google.colab import drive
drive.mount('/content/drive')

# Commented out IPython magic to ensure Python compatibility.
# %cd /content/drive/MyDrive/MSc Computational Neuroscience, Cognition & AI/MLis2/ML Project/code/autopilot-main/
!ls

! pip install -r requirements.txt

! python run.py --model base

! python run.py --model rollin_in_the_deep