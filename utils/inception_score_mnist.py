from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os.path
import sys
import tarfile
import math
import sys

import numpy as np
import tensorflow as tf
from tensorflow.examples.tutorials.mnist import input_data

root_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, root_path)
from dataio.dataset import Dataset
from models.mnist import Mnist
import utils

mnist_model = None
# Call this function with a numpy array which has a shape of [None, 784] and
# with values ranging from 0 to 1
def get_inception_score(mnist_model, images, splits=10):
    bs = 100
    preds = []
    total_samples = images.shape[0]
    n_batches = int(math.ceil(float(total_samples) / float(bs)))
    for i in range(n_batches):
        input = images[(i * bs):min((i + 1) * bs, total_samples)]
        target = np.zeros([input.shape[0], 10])
        dataset = Dataset()
        dataset.build_from_data(input, target)
        fetch = [mnist_model.softmax]
        pred = mnist_model.valid(dataset, fetch)
        preds.append(pred[0])
    preds = np.concatenate(preds, 0)
    scores = []
    for i in range(splits):
        part = preds[(i * preds.shape[0] // splits):((i + 1) * preds.shape[0] // splits), :]
        kl = part * (np.log(part) - np.log(np.expand_dims(np.mean(part, 0), 0)))
        kl = np.mean(np.sum(kl, 1))
        scores.append(np.exp(kl))
    return np.mean(scores), np.std(scores)

def load_mnist_model(config):
    print('init_mnist_model')
    mnist_model = Mnist(config, exp_name='mnist_classification')
    mnist_model.load_model(config.pretrained_mnist_checkpoint_dir)
    return mnist_model
