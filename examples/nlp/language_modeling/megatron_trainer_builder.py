from pytorch_lightning import Trainer
from pytorch_lightning.callbacks import ModelSummary
from pytorch_lightning.plugins.environments import TorchElasticEnvironment
from nemo.collections.nlp.parts.nlp_overrides import (
    GradScaler,
    MegatronHalfPrecisionPlugin,
    NLPDDPStrategy,
    PipelineMixedPrecisionPlugin,
)


class MegatronTrainerBuilder:
    def __init__(self, cfg) -> None:
        self.cfg = cfg

    def _training_strategy(self) -> NLPDDPStrategy:
        return NLPDDPStrategy(
            no_ddp_communication_hook=True,
            gradient_as_bucket_view=self.cfg.model.gradient_as_bucket_view,
            find_unused_parameters=False,
        )

    def _grad_scaler(self) -> GradScaler:
        return GradScaler(
            init_scale=self.cfg.model.get('native_amp_init_scale', 2 ** 32),
            growth_interval=self.cfg.model.get('native_amp_growth_interval', 1000),
            hysteresis=self.cfg.model.get('hysteresis', 2),
        )

    def _plugins(self) -> list:
        megatron_amp_o2 = self.cfg.model.get('megatron_amp_O2', False)
        with_distributed_adam = self.cfg.model.optim.get('name') == 'distributed_fused_adam'

        plugins = []
        if self.cfg.trainer.precision in [16, '16', 'bf16', '16-mixed', 'bf16-mixed']:
            scaler = None
            if self.cfg.trainer.precision == [16, '16', '16-mixed']:
                scaler = self._grad_scaler()
                plugin_precision = '16-mixed'
            else:
                plugin_precision = 'bf16-mixed'

            if megatron_amp_o2 and not with_distributed_adam:
                plugins.append(
                    MegatronHalfPrecisionPlugin(precision=plugin_precision, device='cuda', scaler=scaler)
                )
            else:
                plugins.append(
                    PipelineMixedPrecisionPlugin(precision=plugin_precision, device='cuda', scaler=scaler)
                )

        if self.cfg.get('cluster_type', None) == 'BCP':
            plugins.append(TorchElasticEnvironment())

        return plugins

    def create_trainer(self) -> Trainer:
        strategy = self._training_strategy()
        plugins = self._plugins()
        return Trainer(plugins=plugins, strategy=strategy, **self.cfg.trainer)


class MegatronBertTrainerBuilder(MegatronTrainerBuilder):
    def _grad_scaler(self) -> GradScaler:
        return GradScaler(
            init_scale=self.cfg.model.get('native_amp_init_scale', 2 ** 32),
            growth_interval=self.cfg.model.get('native_amp_growth_interval', 1000),
        )


class MegatronT5TrainerBuilder(MegatronTrainerBuilder):
    def create_trainer(self) -> Trainer:
        strategy = self._training_strategy()
        plugins = self._plugins()
        return Trainer(plugins=plugins, strategy=strategy, **self.cfg.trainer, callbacks=[ModelSummary(max_depth=3)])
