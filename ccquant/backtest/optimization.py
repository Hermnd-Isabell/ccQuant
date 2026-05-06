"""
Parameter optimization for backtesting.
Supports brute-force (multiprocessing) and genetic algorithm (DEAP) optimization.
Mirrors vnpy's OptimizationSetting / run_bf_optimization / run_ga_optimization.
"""

from __future__ import annotations

import multiprocessing
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from itertools import product
from typing import Any


class OptimizationSetting:
    """Defines parameter search space and optimization target."""

    def __init__(self) -> None:
        self.params: dict[str, list] = {}
        self.target_name: str = "sharpe_ratio"

    def add_parameter(
        self,
        name: str,
        start: float,
        end: float | None = None,
        step: float | None = None,
    ) -> None:
        if end is None or step is None:
            self.params[name] = [start]
            return

        value = start
        value_list: list[float] = []
        while value <= end:
            value_list.append(value)
            value += step
        self.params[name] = value_list

    def set_target(self, target_name: str) -> None:
        self.target_name = target_name

    def generate_settings(self) -> list[dict]:
        keys = list(self.params.keys())
        values = list(self.params.values())
        settings: list[dict] = []
        for combo in product(*values):
            setting = dict(zip(keys, combo))
            settings.append(setting)
        return settings


def run_bf_optimization(
    evaluate_func: Callable,
    optimization_setting: OptimizationSetting,
    max_workers: int | None = None,
    output: Callable | None = None,
) -> list[tuple[str, float, dict]]:
    """
    Brute-force optimization using ProcessPoolExecutor.
    evaluate_func(setting) -> (str(setting), target_value, statistics_dict)
    """
    settings = optimization_setting.generate_settings()
    if not settings:
        return []

    if output:
        output(f"开始暴力穷举优化，共{len(settings)}组参数")

    if max_workers is None:
        max_workers = max(1, multiprocessing.cpu_count() - 1)

    results: list[tuple[str, float, dict]] = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(evaluate_func, s): s for s in settings}
        for future in futures:
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                if output:
                    output(f"优化任务异常: {e}")

    results.sort(key=lambda x: x[1], reverse=True)

    if output:
        output(f"暴力穷举优化完成，共{len(results)}组结果")

    return results


def run_ga_optimization(
    evaluate_func: Callable,
    optimization_setting: OptimizationSetting,
    max_workers: int | None = None,
    ngen: int = 30,
    population_size: int = 100,
    output: Callable | None = None,
) -> list[tuple[str, float, dict]]:
    """
    Genetic algorithm optimization using DEAP library.
    Falls back to brute-force if DEAP is not installed.
    """
    try:
        from deap import algorithms, base, creator, tools
    except ImportError:
        if output:
            output("DEAP未安装，回退到暴力穷举优化")
        return run_bf_optimization(
            evaluate_func, optimization_setting, max_workers, output
        )

    if output:
        output(f"开始遗传算法优化，代数={ngen}，种群={population_size}")

    # Build parameter bounds
    param_keys = list(optimization_setting.params.keys())
    param_values = list(optimization_setting.params.values())

    if not param_keys:
        return []

    # DEAP setup
    if hasattr(creator, "FitnessMax"):
        del creator.FitnessMax
    if hasattr(creator, "Individual"):
        del creator.Individual

    creator.create("FitnessMax", base.Fitness, weights=(1.0,))
    creator.create("Individual", list, fitness=creator.FitnessMax)

    toolbox = base.Toolbox()

    # Register attribute generators (index into each param's value list)
    import random

    for i, values in enumerate(param_values):
        toolbox.register(f"attr_{i}", random.choice, values)

    def create_individual():
        ind = []
        for i in range(len(param_keys)):
            ind.append(getattr(toolbox, f"attr_{i}")())
        return creator.Individual(ind)

    toolbox.register("individual", create_individual)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    def evaluate_individual(individual):
        setting = dict(zip(param_keys, individual))
        try:
            result = evaluate_func(setting)
            return (result[1],)
        except Exception:
            return (-float("inf"),)

    toolbox.register("evaluate", evaluate_individual)
    toolbox.register("mate", tools.cxTwoPoint)
    toolbox.register("select", tools.selTournament, tournsize=3)

    def mutate_individual(individual, indpb=0.1):
        for i in range(len(individual)):
            if random.random() < indpb:
                individual[i] = random.choice(param_values[i])
        return (individual,)

    toolbox.register("mutate", mutate_individual)

    # Run GA
    pop = toolbox.population(n=population_size)
    algorithms.eaSimple(pop, toolbox, cxpb=0.5, mutpb=0.1, ngen=ngen, verbose=False)

    # Collect results
    results: list[tuple[str, float, dict]] = []
    seen: set[str] = set()

    for ind in pop:
        setting = dict(zip(param_keys, ind))
        key = str(setting)
        if key in seen:
            continue
        seen.add(key)
        try:
            result = evaluate_func(setting)
            results.append(result)
        except Exception:
            pass

    results.sort(key=lambda x: x[1], reverse=True)

    if output:
        output(f"遗传算法优化完成，共{len(results)}组结果")

    return results
