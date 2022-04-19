#!/usr/bin/env python3

import os
import random
import glob
import argparse
import math

import cv2
import numpy as np
import tensorflow as tf
import tensorflow_addons as tfa
import matplotlib.pyplot as plt
from prettytable import PrettyTable

from utilities.augmentation import Augment, Normalize 



class TFRecordLoader():
    def __init__(self,
                 tfrecords,
                 dims,
                 name,
                 taskType='binary',
                 augmentation=[],
                 augParams={},
                 normalize=[],
                 normalizeParams={}):

        self.tfrecords=tfrecords
        self.dims=dims
        self.name=name
        self.taskType=taskType
        self.augmentations=augmentation
        self.augParams=augParams
        self.normalize=normalize
        self.normalizeParams=normalizeParams
        self.num=self.recordSize()


    def _readTFRecord(self, serialized):
        '''
        read tfrecord image/mask files
        :param serialized: tfrecord file
        :return image: image tensor (HxWxC)
        :return mask: mask tensor (HxWxC)
        '''   
        data = {
            'image': tf.io.FixedLenFeature((), tf.string),
            'mask': tf.io.FixedLenFeature((), tf.string)
            #'imagename': tf.io.FixedLenFeature((), tf.string),
            #'maskname': tf.io.FixedLenFeature((), tf.string)
            #'dims': tf.io.FixedLenFeature((), tf.int64)
               }
        example = tf.io.parse_single_example(serialized, data)
        image = tf.image.decode_png(example['image'])
        mask = tf.image.decode_png(example['mask'])
        return image, mask


    def recordSize(self):
        '''
        return total image count across all tfrecord files (whole dataset)
        :param tfrecords: tfrecord file paths
        :return num: int file count
        '''
        option_no_order = tf.data.Options()
        option_no_order.experimental_deterministic = False
        dataset = tf.data.Dataset.list_files(self.tfrecords)
        dataset = dataset.with_options(option_no_order)
        dataset = dataset.interleave(tf.data.TFRecordDataset, cycle_length=4, num_parallel_calls=4)
        dataset = dataset.map(self._readTFRecord, num_parallel_calls=4)
        for i, d in enumerate(dataset):
            pass
        return i

    
    def _augment(self):
        aug = Augment(self.augParams['hue'], 
                      self.augParams['saturation'], 
                      self.augParams['contrast'], 
                      self.augParams['brightness'], 
                      self.augParams['rotateProb'], 
                      self.augParams['flipProb'], 
                      self.m,augParams['colorProb'])
        print('\n'*2+'Applying following Augmentations to'+self.name+' dataset \n')
        for i, a in enumerate(self.augmentations):
            print('{}: {}'.format(i, a))
        columns = [c for c in list(self.augParams.keys())]
        values = [v for v in list(self.augParams.values())]
        table = PrettyTable(columns)
        table.add_row(values)
        print(table)
        print('\n')
        for f in self.augmentations:
            dataset = dataset.map(getattr(aug, 'get'+f), num_parallel_calls=4)
            #dataset = dataset.map(lambda x, y: (tf.clip_by_value(x, 0, 1), y),  num_parallel_calls=4)


    def _normalize(self):
        norm = Normalize(self.normalizeParams['channelMeans'],self.normalizeParams['channelStd'])
        print('\n'*2+'Applying following normalization methods to '+ self.name+' dataset \n')
        for i, n in enumerate(self.normalize):
            print('{}','{}'.format(i,n))
            dataset = dataset.map(getattr(norm, 'get'+ n), num_parallel_calls=4)
        if 'StandardizeDataset' in self.normalize:
            columns=['means', 'std']
            values=[channelMeans, channelStd]
            table = PrettyTable(columns)
            table.add_row(values)
            print(table)
            print('\n')


    def getShards(self,batchSize): 
        '''
        generate tf.record.dataset containing  image+ mask tensors with 
        transfomations/augmentations.
        tastType: string multi or binary
        :returns dataset: tfrecord.data.dataset
        '''
        AUTO = tf.data.experimental.AUTOTUNE
        ignoreDataOrder = tf.data.Options()
        ignoreDataOrder.experimental_deterministic = False
        dataset = tf.data.Dataset.list_files(self.tfrecords)
        dataset = dataset.with_options(ignoreDataOrder)
        dataset = dataset.interleave(lambda x: tf.data.TFRecordDataset(x), cycle_length=16, num_parallel_calls=AUTO)
        dataset = dataset.map(readTFRecord, num_parallel_calls=AUTO)
        f = lambda x: tf.cast(tf.reshape(x,(self.dims,self.dims, 3)),tf.float16)
        dataset = dataset.map(lambda x, y: (f, f))
        print(self.name+' dataset')
        print('-'*15)
        if len(self.augmentations)>0:
            self._augment()
        else:
            print('No data augmentation')

        if len(self.normalize)>0:
            self._normalize()
        else:
            print('No data normalization')
        dataset = dataset.map(lambda x, y: (x, y[:,:,0:1]), num_parallel_calls=4)
        if self.taskType=='multi':
            dataset = dataset.map(lambda x, y: (x, tf.one_hot(tf.cast(y[:,:,0], tf.int32), depth=3, dtype=tf.float32)), num_parallel_calls=4)
        #batch train and validation datasets (do not use dataset.repeat())
        #since we build our own custom training loop as opposed to model.fit
        #if model.fit used order of shuffle,cache and batch important
        if self.name!='Test':
            dataset = dataset.cache()
            #dataset = dataset.repeat()
            dataset = dataset.shuffle(dataSize, reshuffle_each_iteration=True)
            dataset = dataset.batch(batchSize, drop_remainder=True)
            dataset = dataset.prefetch(AUTO)
        else:
            dataset = dataset.batch(batchSize)
        return dataset


if  __name__ == '__main__':

    ap = argparse.ArgumentParser()
    ap.add_argument('-rp', '--tfrecordpath', required=True, help='path to tfrecord')
    ap.add_argument('-c', '--categorical', help='binary or categorical - default is binary')
    ap.add_argument('-n', '--number', help='get the number of records')
    ap.add_argument('-a', '--augment', help='augmentation flag')
    args = vars(ap.parse_args())

    tfRecordPaths = os.path.join(args['tfrecordpath'],'*.tfrecords')
    if args['number'] is not None:
        number = getRecordNumber(tfrecords)
        print('The number is: {}'.format(number), flush=True)

    dataset = getShards(tfRecordPaths, augment)
