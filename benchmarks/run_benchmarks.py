#!/usr/bin/env python3
"""
Run comprehensive benchmarks for medical data validation.

This script runs various benchmarks to test performance, scalability,
and accuracy of the medical data validator.
"""

import sys
import time
from pathlib import Path
import pandas as pd

# Add the parent directory to the path so we can import our package
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.benchmark_framework import MedicalDataBenchmarker


def main():
    """Run comprehensive benchmarks."""
    
    print("🏥 Medical Data Validator - Benchmark Suite")
    print("=" * 50)
    
    # Initialize benchmarker
    benchmarker = MedicalDataBenchmarker()
    
    print("\n1️⃣  Running scalability benchmarks...")
    scalability_results = benchmarker.run_scalability_benchmarks(max_records=50000)
    
    print("\n2️⃣  Running validation rule benchmarks...")
    rule_results = benchmarker.run_validation_rule_benchmarks(dataset_size=10000)
    
    print("\n3️⃣  Generating benchmark report...")
    report = benchmarker.generate_report()
    
    # Save results
    results_file = benchmarker.save_results()
    print(f"\n📊 Results saved to: {results_file}")
    
    # Generate plots
    plot_files = benchmarker.plot_performance()
    if plot_files:
        print(f"📈 Plots generated: {len(plot_files)} files")
        for plot_file in plot_files:
            print(f"   - {plot_file}")
    
    # Print report
    print("\n" + "=" * 50)
    print("📋 BENCHMARK REPORT")
    print("=" * 50)
    print(report)
    
    print("\n✅ Benchmark suite completed successfully!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 