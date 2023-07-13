# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import torch.multiprocessing as mp
from megatron_trainer_builder import MegatronBertTrainerBuilder
from omegaconf.omegaconf import OmegaConf, open_dict
from pytorch_lightning import Trainer
from pytorch_lightning.plugins.environments import TorchElasticEnvironment
from pytorch_lightning.trainer.connectors.checkpoint_connector import _CheckpointConnector

from nemo.collections.nlp.models.language_modeling.megatron_bert_model import MegatronBertModel
from nemo.core.config import hydra_runner
from nemo.utils import logging
from nemo.utils.exp_manager import exp_manager


@hydra_runner(config_path="conf", config_name="megatron_bert_config")
def main(cfg) -> None:
    if cfg.model.data.dataloader_type != "LDDL":
        mp.set_start_method("spawn", force=True)

    logging.info("\n\n************** Experiment configuration ***********")
    logging.info(f'\n{OmegaConf.to_yaml(cfg)}')

    trainer = MegatronBertTrainerBuilder(cfg).create_trainer()

    exp_manager(trainer, cfg.exp_manager)

    # update resume from checkpoint found by exp_manager
    # Avoid calling protected API trainer._checkpoint_connector._ckpt_path as lightning 2.0 supports ckpt_path as trainer arg
    resume_from_checkpoint = trainer.ckpt_path
    # resume_from_checkpoint = uninject_model_parallel_rank(resume_from_checkpoint)
    logging.info(f'Resuming training from checkpoint: {resume_from_checkpoint}')

    trainer._checkpoint_connector = _CheckpointConnector(trainer)

    # hydra interpolation does not work here as the interpolation key is lost when PTL saves hparams
    with open_dict(cfg):
        cfg.model.precision = cfg.trainer.precision

    model = MegatronBertModel(cfg.model, trainer)

    trainer.fit(model)


if __name__ == '__main__':
    main()
