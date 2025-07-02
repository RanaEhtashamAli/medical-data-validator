"""
Benchmarking framework for medical data validation performance testing.

This module provides tools to benchmark validation performance across different
dataset sizes, validation rules, and data types.
"""

import time
import statistics
import json
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

# Optional imports for plotting
try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False

from medical_data_validator.core import MedicalDataValidator, ValidationResult
from medical_data_validator.validators import (
    SchemaValidator,
    PHIDetector,
    DataQualityChecker,
    MedicalCodeValidator,
    RangeValidator,
    DateValidator,
)


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""
    dataset_name: str
    dataset_size: int
    validation_rules: List[str]
    execution_time: float
    memory_usage: Optional[float] = None
    issues_found: int = 0
    validation_success: bool = True
    error_message: Optional[str] = None


class MedicalDataBenchmarker:
    """Comprehensive benchmarking tool for medical data validation."""
    
    def __init__(self, output_dir: str = "benchmark_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.results: List[BenchmarkResult] = []
        
    def benchmark_dataset(
        self,
        dataset: pd.DataFrame,
        dataset_name: str,
        validators: Optional[List[Callable]] = None,
        iterations: int = 3
    ) -> List[BenchmarkResult]:
        """Benchmark validation performance on a dataset."""
        
        if validators is None:
            validators = self._get_default_validators()
        
        results = []
        
        for i in range(iterations):
            print(f"Running benchmark {i+1}/{iterations} for {dataset_name}...")
            
            # Create validator
            validator = MedicalDataValidator()
            for validator_func in validators:
                validator_func(validator)
            
            # Time the validation
            start_time = time.time()
            try:
                result = validator.validate(dataset)
                execution_time = time.time() - start_time
                
                benchmark_result = BenchmarkResult(
                    dataset_name=dataset_name,
                    dataset_size=len(dataset),
                    validation_rules=[v.__class__.__name__ for v in validator.rules],
                    execution_time=execution_time,
                    issues_found=len(result.issues),
                    validation_success=result.is_valid
                )
                
            except Exception as e:
                execution_time = time.time() - start_time
                benchmark_result = BenchmarkResult(
                    dataset_name=dataset_name,
                    dataset_size=len(dataset),
                    validation_rules=[v.__class__.__name__ for v in validator.rules],
                    execution_time=execution_time,
                    validation_success=False,
                    error_message=str(e)
                )
            
            results.append(benchmark_result)
        
        self.results.extend(results)
        return results
    
    def _get_default_validators(self) -> List[Callable]:
        """Get default set of validators for benchmarking."""
        return [
            lambda v: v.add_rule(SchemaValidator()),
            lambda v: v.add_rule(PHIDetector()),
            lambda v: v.add_rule(DataQualityChecker()),
        ]
    
    def generate_synthetic_medical_data(
        self,
        num_records: int,
        include_phi: bool = True,
        include_errors: bool = True
    ) -> pd.DataFrame:
        """Generate synthetic medical data for benchmarking."""
        
        np.random.seed(42)  # For reproducible results
        
        data = {
            'patient_id': [f"P{i:06d}" for i in range(num_records)],
            'age': np.random.randint(0, 120, num_records),
            'gender': np.random.choice(['M', 'F'], num_records),
            'diagnosis_code': np.random.choice([
                'A01.1', 'B02.2', 'C03.3', 'D04.4', 'E05.5',
                'F06.6', 'G07.7', 'H08.8', 'I09.9', 'J10.0'
            ], num_records),
            'temperature': np.random.normal(98.6, 2, num_records),
            'blood_pressure_systolic': np.random.normal(120, 20, num_records),
            'blood_pressure_diastolic': np.random.normal(80, 10, num_records),
            'admission_date': pd.date_range(
                start='2020-01-01', 
                periods=num_records, 
                freq='D'
            ),
        }
        
        if include_phi:
            # Generate realistic PHI data
            data.update({
                'patient_name': [f"Patient_{i}" for i in range(num_records)],
                'email': [f"patient_{i}@example.com" for i in range(num_records)],
                'phone': [f"555-{i:03d}-{i:04d}" for i in range(num_records)],
                'ssn': [f"123-45-{i:04d}" for i in range(num_records)],
            })
        
        if include_errors:
            # Add some intentional errors
            error_indices = np.random.choice(
                num_records, 
                size=num_records//10, 
                replace=False
            )
            for idx in error_indices:
                data['age'][idx] = np.random.randint(150, 200)  # Invalid age
                data['diagnosis_code'][idx] = 'INVALID_CODE'
                data['temperature'][idx] = np.random.uniform(200, 300)  # Invalid temp
        
        return pd.DataFrame(data)
    
    def run_scalability_benchmarks(self, max_records: int = 100000) -> Dict[str, List[BenchmarkResult]]:
        """Run benchmarks across different dataset sizes."""
        
        sizes = [100, 1000, 10000, 50000, 100000]
        sizes = [s for s in sizes if s <= max_records]
        
        scalability_results = {}
        
        for size in sizes:
            print(f"\nGenerating dataset with {size:,} records...")
            dataset = self.generate_synthetic_medical_data(size)
            
            results = self.benchmark_dataset(
                dataset=dataset,
                dataset_name=f"synthetic_{size}",
                iterations=3
            )
            
            scalability_results[f"{size}_records"] = results
        
        return scalability_results
    
    def run_validation_rule_benchmarks(self, dataset_size: int = 10000) -> Dict[str, List[BenchmarkResult]]:
        """Benchmark different validation rule combinations."""
        
        dataset = self.generate_synthetic_medical_data(dataset_size)
        
        rule_combinations = {
            "schema_only": [lambda v: v.add_rule(SchemaValidator())],
            "phi_only": [lambda v: v.add_rule(PHIDetector())],
            "quality_only": [lambda v: v.add_rule(DataQualityChecker())],
            "medical_codes": [lambda v: v.add_rule(MedicalCodeValidator(
                code_columns={"diagnosis_code": "icd10"}
            ))],
            "ranges": [lambda v: v.add_rule(RangeValidator(
                ranges={"age": {"min": 0, "max": 120}}
            ))],
            "dates": [lambda v: v.add_rule(DateValidator(
                date_columns=["admission_date"]
            ))],
            "all_rules": [
                lambda v: v.add_rule(SchemaValidator()),
                lambda v: v.add_rule(PHIDetector()),
                lambda v: v.add_rule(DataQualityChecker()),
                lambda v: v.add_rule(MedicalCodeValidator(
                    code_columns={"diagnosis_code": "icd10"}
                )),
                lambda v: v.add_rule(RangeValidator(
                    ranges={"age": {"min": 0, "max": 120}}
                )),
                lambda v: v.add_rule(DateValidator(
                    date_columns=["admission_date"]
                )),
            ]
        }
        
        rule_results = {}
        
        for rule_name, validators in rule_combinations.items():
            print(f"\nBenchmarking {rule_name}...")
            results = self.benchmark_dataset(
                dataset=dataset,
                dataset_name=f"rule_test_{rule_name}",
                validators=validators,
                iterations=3
            )
            rule_results[rule_name] = results
        
        return rule_results
    
    def generate_report(self) -> str:
        """Generate a comprehensive benchmark report."""
        
        if not self.results:
            return "No benchmark results available."
        
        report = []
        report.append("Medical Data Validator - Benchmark Report")
        report.append("=" * 50)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total benchmark runs: {len(self.results)}")
        report.append("")
        
        # Group results by dataset
        datasets = {}
        for result in self.results:
            if result.dataset_name not in datasets:
                datasets[result.dataset_name] = []
            datasets[result.dataset_name].append(result)
        
        # Summary statistics
        report.append("SUMMARY STATISTICS")
        report.append("-" * 20)
        
        for dataset_name, results in datasets.items():
            if not results:
                continue
                
            times = [r.execution_time for r in results if r.validation_success]
            if times:
                avg_time = statistics.mean(times)
                std_time = statistics.stdev(times) if len(times) > 1 else 0
                min_time = min(times)
                max_time = max(times)
                
                report.append(f"\n{dataset_name}:")
                report.append(f"  Dataset size: {results[0].dataset_size:,} records")
                report.append(f"  Average time: {avg_time:.4f}s (±{std_time:.4f}s)")
                report.append(f"  Time range: {min_time:.4f}s - {max_time:.4f}s")
                report.append(f"  Success rate: {len(times)}/{len(results)} ({len(times)/len(results)*100:.1f}%)")
        
        # Performance analysis
        report.append("\n\nPERFORMANCE ANALYSIS")
        report.append("-" * 20)
        
        # Scalability analysis
        scalability_data = {}
        for dataset_name, results in datasets.items():
            if 'synthetic_' in dataset_name:
                size = int(dataset_name.split('_')[1])
                avg_time = statistics.mean([r.execution_time for r in results if r.validation_success])
                scalability_data[size] = avg_time
        
        if scalability_data:
            report.append("\nScalability (Time vs Dataset Size):")
            for size in sorted(scalability_data.keys()):
                report.append(f"  {size:,} records: {scalability_data[size]:.4f}s")
        
        # Rule performance analysis
        rule_data = {}
        for dataset_name, results in datasets.items():
            if 'rule_test_' in dataset_name:
                rule_name = dataset_name.split('rule_test_')[1]
                avg_time = statistics.mean([r.execution_time for r in results if r.validation_success])
                rule_data[rule_name] = avg_time
        
        if rule_data:
            report.append("\nValidation Rule Performance:")
            for rule_name, avg_time in sorted(rule_data.items(), key=lambda x: x[1]):
                report.append(f"  {rule_name}: {avg_time:.4f}s")
        
        return "\n".join(report)
    
    def save_results(self, filename: Optional[str] = None) -> str:
        """Save benchmark results to file."""
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_results_{timestamp}.json"
        
        filepath = self.output_dir / filename
        
        # Convert results to serializable format
        serializable_results = []
        for result in self.results:
            serializable_results.append({
                'dataset_name': result.dataset_name,
                'dataset_size': result.dataset_size,
                'validation_rules': result.validation_rules,
                'execution_time': result.execution_time,
                'memory_usage': result.memory_usage,
                'issues_found': result.issues_found,
                'validation_success': result.validation_success,
                'error_message': result.error_message,
            })
        
        with open(filepath, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        
        return str(filepath)
    
    def plot_performance(self, save_plots: bool = True) -> List[str]:
        """Generate performance visualization plots."""
        
        if not PLOTTING_AVAILABLE:
            print("Warning: matplotlib/seaborn not available. Skipping plots.")
            return []
        
        if not self.results:
            return []
        
        plot_files = []
        
        # Group results by dataset
        datasets = {}
        for result in self.results:
            if result.dataset_name not in datasets:
                datasets[result.dataset_name] = []
            datasets[result.dataset_name].append(result)
        
        # Scalability plot
        scalability_data = {}
        for dataset_name, results in datasets.items():
            if 'synthetic_' in dataset_name:
                size = int(dataset_name.split('_')[1])
                times = [r.execution_time for r in results if r.validation_success]
                if times:
                    scalability_data[size] = statistics.mean(times)
        
        if scalability_data:
            plt.figure(figsize=(10, 6))
            sizes = sorted(scalability_data.keys())
            times = [scalability_data[size] for size in sizes]
            
            plt.plot(sizes, times, 'bo-', linewidth=2, markersize=8)
            plt.xlabel('Dataset Size (records)')
            plt.ylabel('Average Execution Time (seconds)')
            plt.title('Validation Performance vs Dataset Size')
            plt.grid(True, alpha=0.3)
            plt.yscale('log')
            plt.xscale('log')
            
            if save_plots:
                plot_file = self.output_dir / "scalability_plot.png"
                plt.savefig(plot_file, dpi=300, bbox_inches='tight')
                plot_files.append(str(plot_file))
            
            plt.close()
        
        # Rule performance plot
        rule_data = {}
        for dataset_name, results in datasets.items():
            if 'rule_test_' in dataset_name:
                rule_name = dataset_name.split('rule_test_')[1]
                times = [r.execution_time for r in results if r.validation_success]
                if times:
                    rule_data[rule_name] = statistics.mean(times)
        
        if rule_data:
            plt.figure(figsize=(12, 6))
            rules = list(rule_data.keys())
            times = list(rule_data.values())
            
            bars = plt.bar(rules, times, color='skyblue', alpha=0.7)
            plt.xlabel('Validation Rules')
            plt.ylabel('Average Execution Time (seconds)')
            plt.title('Performance by Validation Rule Type')
            plt.xticks(rotation=45, ha='right')
            plt.grid(True, alpha=0.3, axis='y')
            
            # Add value labels on bars
            for bar, time_val in zip(bars, times):
                plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
                        f'{time_val:.4f}s', ha='center', va='bottom')
            
            if save_plots:
                plot_file = self.output_dir / "rule_performance_plot.png"
                plt.savefig(plot_file, dpi=300, bbox_inches='tight')
                plot_files.append(str(plot_file))
            
            plt.close()
        
        return plot_files 