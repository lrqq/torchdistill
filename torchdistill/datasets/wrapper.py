import os

import numpy as np
import torch
from torch.utils.data import Dataset

from .registry import register_dataset_wrapper
from ..common import file_util
from ..common.constant import def_logger

logger = def_logger.getChild(__name__)


def default_idx2subpath(index):
    """
    Converts index to a file path including a parent dir name, which consists of the last four digits of the index.

    :param index: index.
    :type index: int
    :return: file path with a parent directory.
    :rtype: str
    """
    digits_str = '{:04d}'.format(index)
    return os.path.join(digits_str[-4:], digits_str)


class BaseDatasetWrapper(Dataset):
    """
    A base dataset wrapper. This is a subclass of :class:`torch.utils.data.Dataset`.

    :param org_dataset: original dataset to be wrapped.
    :type org_dataset: torch.utils.data.Dataset
    """
    def __init__(self, org_dataset):
        self.org_dataset = org_dataset

    def __getitem__(self, index):
        sample, target = self.org_dataset.__getitem__(index)
        return sample, target, dict()

    def __len__(self):
        return len(self.org_dataset)


class CacheableDataset(BaseDatasetWrapper):
    """
    A dataset wrapper that additionally loads cached files in ``cache_dir_path`` if exists.

    :param org_dataset: original dataset to be wrapped.
    :type org_dataset: torch.utils.data.Dataset
    :param cache_dir_path: cache directory path.
    :type cache_dir_path: str
    :param idx2subpath_func: function to convert a sample index to a file path.
    :type idx2subpath_func: typing.Callable or None
    :param ext: cache file extension.
    :type ext: str
    """
    def __init__(self, org_dataset, cache_dir_path, idx2subpath_func=None, ext='.pt'):
        super().__init__(org_dataset)
        self.cache_dir_path = cache_dir_path
        self.idx2subath_func = str if idx2subpath_func is None else idx2subpath_func
        self.ext = ext

    def __getitem__(self, index):
        sample, target, supp_dict = super().__getitem__(index)
        cache_file_path = os.path.join(self.cache_dir_path, self.idx2subath_func(index) + self.ext)
        if file_util.check_if_exists(cache_file_path):
            cached_data = torch.load(cache_file_path)
            supp_dict['cached_data'] = cached_data

        supp_dict['cache_file_path'] = cache_file_path
        return sample, target, supp_dict


@register_dataset_wrapper
class CRDDatasetWrapper(BaseDatasetWrapper):
    """
    A dataset wrapper for Contrastive Representation Distillation (CRD).

    Yonglong Tian, Dilip Krishnan, Phillip Isola: `"Contrastive Representation Distillation" <https://openreview.net/forum?id=SkgpBJrtvS>`_ @ ICLR 2020 (2020)

    :param org_dataset: original dataset to be wrapped.
    :type org_dataset: torch.utils.data.Dataset
    :param num_negative_samples: number of negative samples for CRD.
    :type num_negative_samples: int
    :param mode: either 'exact' or 'relax'.
    :type mode: str
    :param ratio: ratio of class-wise negative samples.
    :type ratio: float
    """
    def __init__(self, org_dataset, num_negative_samples, mode, ratio):
        super().__init__(org_dataset)
        self.num_negative_samples = num_negative_samples
        self.mode = mode
        num_classes = len(org_dataset.classes)
        num_samples = len(org_dataset)
        labels = org_dataset.targets
        self.cls_positives = [[] for i in range(num_classes)]
        for i in range(num_samples):
            self.cls_positives[labels[i]].append(i)

        self.cls_negatives = [[] for i in range(num_classes)]
        for i in range(num_classes):
            for j in range(num_classes):
                if j == i:
                    continue
                self.cls_negatives[i].extend(self.cls_positives[j])

        self.cls_positives = [np.asarray(self.cls_positives[i]) for i in range(num_classes)]
        self.cls_negatives = [np.asarray(self.cls_negatives[i]) for i in range(num_classes)]
        if 0 < ratio < 1:
            n = int(len(self.cls_negatives[0]) * ratio)
            self.cls_negatives = [np.random.permutation(self.cls_negatives[i])[0:n] for i in range(num_classes)]

        self.cls_positives = self.cls_positives
        self.cls_negatives = self.cls_negatives

    def __getitem__(self, index):
        sample, target, supp_dict = super().__getitem__(index)
        if self.mode == 'exact':
            pos_idx = index
        elif self.mode == 'relax':
            pos_idx = np.random.choice(self.cls_positives[target], 1)
            pos_idx = pos_idx[0]
        else:
            raise NotImplementedError(self.mode)

        replace = True if self.num_negative_samples > len(self.cls_negatives[target]) else False
        neg_idx = np.random.choice(self.cls_negatives[target], self.num_negative_samples, replace=replace)
        contrast_idx = np.hstack((np.asarray([pos_idx]), neg_idx))
        supp_dict['pos_idx'] = index
        supp_dict['contrast_idx'] = contrast_idx
        return sample, target, supp_dict


@register_dataset_wrapper
class SSKDDatasetWrapper(BaseDatasetWrapper):
    """
    A dataset wrapper for Self-Supervised Knowledge Distillation (SSKD).

    Guodong Xu, Ziwei Liu, Xiaoxiao Li, Chen Change Loy: `"Knowledge Distillation Meets Self-Supervision" <https://www.ecva.net/papers/eccv_2020/papers_ECCV/html/898_ECCV_2020_paper.php>`_ @ ECCV 2020 (2020)

    :param org_dataset: original dataset to be wrapped.
    :type org_dataset: torch.utils.data.Dataset
    """
    def __init__(self, org_dataset):
        super().__init__(org_dataset)
        self.transform = org_dataset.transform
        org_dataset.transform = None

    def __getitem__(self, index):
        # Assume sample is a PIL Image
        sample, target, supp_dict = super().__getitem__(index)
        sample = torch.stack([self.transform(sample).detach(),
                              self.transform(sample.rotate(90, expand=True)).detach(),
                              self.transform(sample.rotate(180, expand=True)).detach(),
                              self.transform(sample.rotate(270, expand=True)).detach()])
        return sample, target, supp_dict

@register_dataset_wrapper
class LeafDatasetWrapper(Dataset):
    """
    A dataset wrapper for MFCC and Leaf

    :param org_dataset: original dataset to be wrapped.
    :type org_dataset: torch.utils.data.Dataset
    """
    def __init__(self, org_dataset):
        self.org_dataset = org_dataset

    def __getitem__(self, index):
        feats, waveform, target = self.org_dataset.__getitem__(index)
        return feats, waveform, target, dict()

    def __len__(self):
        return len(self.org_dataset)