'''
utilities.py: useful functions


"""
preprocessing.py: perform operations on patch dataset

1. calcutate_std_mean: calculate mean and standard deviation of pixel intensities
2. calculate_weights: generate weights proportional to inverse of class area. Useful to 
   tackle class imbalance for ML training
"""
'''

import os 
import glob
from itertools import chain

import cv2
import numpy as np
import xml.etree.ElementTree as ET
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib as mpl  
import matplotlib.patches as patches
from skimage.color import rgb2gray
from skimage.filters import threshold_otsu
from skimage.morphology import square, closing, opening


def mask2rgb(mask):
    n_classes=len(np.unique(mask))
    colors=sns.color_palette('hls',n_classes)
    rgb_mask=np.zeros(mask.shape+(3,))
    for c in range(1,n_classes+1):
        t=(mask==c)
        rgb_mask[:,:,0][t]=colors[c-1][0]
        rgb_mask[:,:,1][t]=colors[c-1][1]
        rgb_mask[:,:,2][t]=colors[c-1][2]
    return rgb_mask


def draw_boundary(annotations, offset=100):

    annotations = list(chain(*[annotations[f] for f in annotations]))
    coords = list(chain(*annotations))
    boundaries = list(map(lambda x: (min(x)-offset, max(x)+offset), list(zip(*coords))))
   
    return boundaries


def oneHotToMask(onehot):
    nClasses =  onehot.shape[-1]
    idx = tf.argmax(onehot, axis=-1)
    colors = sns.color_palette('hls', nClasses)
    multimask = tf.gather(colors, idx)
    multimask = np.where(multimask[:,:,:]==colors[0], 0, multimask[:,:,:])

    return multimask


#can we sample and return a new patching object
def sample_patches(patch,n,replacement=False):
    
    if replacement:
        patches=random.choice(patch._patches,n)
    else:
        patches=random.sample(patch._patches,n)

    new_patch =  Patch(patch.slide,
                       patch.size,
                       patch.mag_level,
                       patch.border,  
                       patch.step)

    new_patch.patches=patches
    return new_patches


class TissueDetect():

    bilateral_args=[
            #{"d":9,"sigmaColor":10000,"sigmaSpace":150},
            {"d":90,"sigmaColor":5000,"sigmaSpace":5000},
            {"d":90,"sigmaColor":5000,"sigmaSpace":5000},
            {"d":90,"sigmaColor":10000,"sigmaSpace":10000},
            {"d":90,"sigmaColor":10000,"sigmaSpace":100}
            ]

    thresh_args=[
            {"thresh":0,"maxval":255,"type":cv2.THRESH_TRUNC+cv2.THRESH_OTSU},
            {"thresh":0,"maxval":255,"type":cv2.THRESH_OTSU}
            ]

    def __init__(self, slide):
        self.slide=openslide.OpenSlide(slide) if isinstance(slide, str) else slide
        self.tissue_mask=None 
        self.contour_mask=None
        self._border=None


    @property
    def tissue_thumbnail(self):
        contours=self._generate_tissue_contour()
        image=self.slide.get_thumbnail(self.slide.level_dimensions[3])
        image=np.array(image.convert('RGB'))
        cv2.drawContours(image, contours, -1, (0, 255, 0), 5)
        x,y,w,h=cv2.boundingRect(np.concatenate(contours))
        cv2.rectangle(image,(x,y),(x+w,y+h),(255,0,0),5)

        return image
        

    def border(self,mag_level):

        test=cv2.resize(self.contour_mask,self.slide.dimensions)
        contours,_=cv2.findContours(test,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)

        #test=cv2.resize(self.contour_mask,self.slide.dimensions)
        #image=self.slide.get_thumbnail(self.slide.level_dimensions[3])
        #image=np.array(image.convert('RGB'))
        #contour=contours[np.argmax([c.size for c in contours])]
        x,y,w,h=cv2.boundingRect(np.concatenate(contours))
        #x,y,w,h=[d*int(self.slide.level_downsamples[mag_level]) for d in [x,y,w,h]]
        self._border=((x,y),(x+w,y+h))
        return self._border
        

    def detect_tissue(self,mask_level):
    
        image = self.slide.read_region((0,0),mask_level, 
                    self.slide.level_dimensions[mask_level]) 

        image = self.slide.get_thumbnail(self.slide.level_dimensions[mask_level]) 
        image = np.array(image.convert('RGB'))
        gray = rgb2gray(image)
        gray_f = gray.flatten()

        pixels_int = gray_f[np.logical_and(gray_f > 0.1, gray_f < 0.98)]
        t = threshold_otsu(pixels_int)
        thresh = np.logical_and(gray_f<t, gray_f>0.1).reshape(gray.shape)
        
        mask = opening(closing(thresh, selem=square(2)), selem=square(2))
        self.tissue_mask = mask.astype(np.uint8)
        
        return cv2.resize(mask.astype(np.uint8),self.slide.dimensions)


    def _generate_tissue_contour(self):
        slide=self.slide.get_thumbnail(self.slide.level_dimensions[3])
        slide=np.array(slide.convert('RGB'))
        img_hsv=cv2.cvtColor(slide,cv2.COLOR_RGB2HSV)
        lower_red=np.array([120,0,0])
        upper_red=np.array([180,255,255])
        mask=cv2.inRange(img_hsv,lower_red,upper_red)
        img_hsv=cv2.cvtColor(img_hsv,cv2.COLOR_HSV2RGB)
        m=cv2.bitwise_and(slide,slide,mask=mask)
        im_fill=np.where(m==0,233,m)
        mask=np.zeros(slide.shape)
        gray=cv2.cvtColor(im_fill,cv2.COLOR_BGR2GRAY)
        
        for b in TissueDetect.bilateral_args:
            gray=cv2.bilateralFilter(np.bitwise_not(gray),**b)
        blur=255-gray
        
        for t in TissueDetect.thresh_args:
            _,blur=cv2.threshold(blur,**t)
        
        self.contour_mask=blur
        contours,_=cv2.findContours(blur,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
        self.contours=contours
        return self.contours


def get_x_y_from_0(slide, point_0, level, integer=True):
    """
    Given a point point_0 = (x0, y0) at level 0, this function will return 
    the coordinates associated to the level 'level' of this point point_l = (x_l, y_l).
    Inverse function of get_x_y
    Args:
        slide : Openslide object from which we extract.
        point_0 : A tuple, or tuple like object of size 2 with integers.
        level : Integer, level to convert to.  
        integer : Boolean, by default True. Wether or not to round
                  the output.
    Returns:
        A tuple corresponding to the converted coordinates, point_l.
    """
    x_0, y_0 = point_0
    size_x_l = slide.level_dimensions[level][0]
    size_y_l = slide.level_dimensions[level][1]
    size_x_0 = float(slide.level_dimensions[0][0])
    size_y_0 = float(slide.level_dimensions[0][1])
  
    x_l = x_0 * size_x_l / size_x_0
    y_l = y_0 * size_y_l / size_y_0
    if integer:
        point_l = (round(x_l), round(y_l))
    else:
        point_l = (x_l, y_l)
    return point_l


def get_size(slide, size_from, level_from, level_to, integer=True):
    """
    Given a size (size_from) at a certain level (level_from), this function will return
    a new size (size_to) but at a different level (level_to).
    Args:
        slide : Openslide object from which we extract.
        size_from : A tuple, or tuple like object of size 2 with integers.
        level_from : Integer, initial level.
        level_to : Integer, final level.
        integer : Boolean, by default True. Wether or not to round
                  the output.
        Returns:
            A tuple, or tuple like object of size 2 with integers corresponding 
            to the new size at level level_to. Or size_to.
    """
    size_x, size_y = size_from
    downsamples = slide.level_downsamples
    scal = float(downsamples[level_from]) / downsamples[level_to]
    if integer:
        func_round = round
    else:
        func_round = lambda x: x
    size_x_new = func_round(float(size_x) * scal)
    size_y_new = func_round(float(size_y) * scal)
    size_to = size_x_new, size_y_new
    return size_to


def visualise_wsi_tiling(
        wsi, 
        tiler,
        save_path,
        viewing_res=3,
        plot_args={'color':'red','size': (12, 12), 'title': ""}):
    
    mpl.use('Agg')
    wsi_thumb = wsi.get_thumbnail(wsi.level_dimensions[viewing_res]) 
    wsi_thumb = np.array(wsi_thumb.convert('RGB'))
    fig, ax = plt.subplots(figsize=plot_args['size'])
    ax.imshow(wsi_thumb)
    for t_xy in tiler.tiles:
        x=int(t_xy[0]/wsi.level_downsamples[viewing_res])
        y=int(t_xy[1]/wsi.level_downsamples[viewing_res])
        w=int(tiler.tile_dims[0]/wsi.level_downsamples[viewing_res])
        h=int(tiler.tile_dims[1]/wsi.level_downsamples[viewing_res])
        patch = patches.Rectangle((y,x), w, h, 
                fill=False, edgecolor=plot_args['color'])
        ax.add_patch(patch)

    ax.set_title(plot_args['title'], size=20)
    ax.axis('off')
    plt.savefig(save_path)


def entropy(tile, threshold):
    avg_entropy=image_entropy(tile)
    if avg_entropy<threshold:
        return True
    

def tile_intensity(tile, threshold, channel=None):
        
    if channel is not None:
        if np.mean(tile[:,:,channel]) > threshold:
            return True

    elif channel is None:
        if np.mean(tile)>threshold:
            return True


def calculate_std_mean(patch_path, channel=True, norm=True):
    """
    returns standard deviation and mean of patches
    :param patch_path: path to patches
    :param channel: boolean default value True
    :param norm: normalize values 0-255->0-1
    :return mean: list of channel means
    :return std: list of channel std
    """
    if patch_path is not None:
        patches = glob.glob(os.path.join(patch_path,'*'))
    shape = cv2.imread(patches[0]).shape
    channels = shape[-1]
    chnl_values = np.zeros((channels))
    chnl_values_sqrt = np.zeros((channels))
    pixel_nums = len(patches)*shape[0]*shape[1]
    print('total number pixels: {}'.format(pixel_nums))
    axis=(0,1,2) if not channel else (0,1)
    divisor=1.0 if not norm else 255.0
    for path in patches:
        patch = cv2.imread(path)
        patch = (patch/divisor).astype('float64')
        chnl_values += np.sum(patch, axis=axis, dtype='float64')
    mean=chnl_values/pixel_nums  
    for path in patches:
        patch = cv2.imread(path)
        patch = (patch/divisor).astype('float64')
        chnl_values_sqrt += np.sum(np.square(patch-mean), axis=axis, dtype='float64')
    std=np.sqrt(chnl_values_sqrt/pixel_nums, dtype='float64')
    print('mean: {}, std: {}'.format(mean, std))
    return mean, std 



def calculate_weights(mask_path,num_cls):

    if mask_path is not None:
        mask_files = glob.glob(os.path.join(mask_path,'*'))
    cls_nums = {c:0 for c in range(num_cls)}
    for f in mask_files:
        mask = cv2.imread(f)
        pixels = mask.reshape(-1)
        classes = np.unique(pixels, return_counts=True)
        pixelDict = dict(list(zip(*classes)))     
        for k, v in pixelDict.items():
            cls_nums[k] = cls_nums[k] + v
    total = sum(list(cls_nums.values()))
    weights = [v/total for v in list(cls_nums.values())]
    print(weights)
    weights = [1/w for w in weights]
    print(weights)
    return weights
    






























#import openslide
#slide_path='/Users/w2030634/CancerHub/TNT/gScarNet/wsis/TCGA-GM-A2DH.svs'
#slide=openslide.OpenSlide(slide_path)
#td=TissueDetect(slide)

#mask=td.detect_tissue(3)
#contours=td._generate_tissue_contour()
#print(td.border)
#cv2.imwrite('thumbnail.png',td.tissue_thumbnail)

#print(mask)
#cv2.imwrite('greg2.png',mask.astype(np.uint8)*255)
