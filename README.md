# Evaluation of Large Language Models for Automated Diagnosis in Brain MRI Reporting

This repository contains the open-source implementation for the research paper "Evaluation of Large Language Models for Automated Diagnosis in Brain MRI Reporting: A Multicenter Benchmark and Reader Study".

## Overview

This project evaluates the performance of large language models (LLMs) in automated brain MRI report analysis and diagnosis generation. The system processes unstructured MRI reports and generates structured diagnostic conclusions using state-of-the-art language models deployed via VLLM.

## Repository Structure

The repository consists of three main components:

### 1. `prompt.py` - Prompt Engineering Module
Contains all system prompts for different tasks and languages:
- **Report Structuring Prompts**: `SYSTEM_PROMPT_FINDINGS_CHINESE` and `SYSTEM_PROMPT_FINDINGS_ENGLISH` for converting unstructured MRI reports into standardized formats
- **Diagnosis Generation Prompts**: Multiple prompt variants for diagnostic reasoning:
  - `FINDINGS_TO_CONCLUSION_PROMPT_TOP1_*`: Single most likely diagnosis
  - `FINDINGS_TO_CONCLUSION_PROMPT_TOP3_*`: Top 3 differential diagnoses
  - `FINDINGS_TO_CONCLUSION_PROMPT_FREE_*`: Flexible diagnosis approach
- **Language Support**: Both Chinese and English variants for all prompts
- **Disease Classification**: 16 standardized brain pathology categories including normal findings, white matter hyperintensities, cerebral atrophy, acute/subacute infarction, and various other brain lesions

### 2. `finding_structure.py` - Report Structuring Module
Processes raw MRI reports to extract and structure findings:
- **Input Processing**: Handles JSON files containing medical reports with original findings and conclusions
- **AI-Powered Structuring**: Uses DeepSeek models to clean and standardize report content
- **Output Generation**: 
  - Individual JSON files for each processed report
  - Consolidated Excel files for batch analysis
- **Structured Extraction**: Separates overall findings summary from disease-specific findings
- **Concurrent Processing**: Multi-threaded processing for efficient batch operations

### 3. `diagnosis_from_findings.py` - Diagnostic Inference Module
Generates diagnostic conclusions from structured findings:
- **Multiple Inference Modes**:
  - `direct`: Uses original findings directly
  - `struct`: Uses pre-structured findings
- **Flexible Prompting**: Supports different diagnostic approaches (top1, top3, free)
- **Model Compatibility**: Configured for various LLMs with specific parameters
- **Clinical Information Integration**: Optional inclusion of clinical context
- **Robust Processing**: Retry mechanisms and error handling for API reliability
- **Output Management**: Comprehensive result storage with reasoning traces

## System Requirements

### Hardware Specifications
- **Deployment Platform**: NVIDIA-H20 with 141GB memory each card
- **GPU Configuration**:
  - DeepSeek models: 8 GPUs
  - Qwen3 models: 4 GPUs  
  - Other models: Single GPU

### Software Dependencies
- **Python**: 3.11.7
- **OpenAI API**: 1.71.0
- **Pandas**: 2.1.4
- **Additional packages**: `concurrent.futures`, `tqdm`, `argparse`, `json`

### VLLM Deployment
All models are deployed using Docker containers with VLLM:
- Each model uses the officially recommended VLLM version
- Docker-based deployment for scalability and consistency
- OpenAI-compatible API endpoints for seamless integration

## Installation

1. **Clone the repository**:
```bash
git clone [repository-url]
cd [repository-name]
```

2. **Install Python dependencies**:
```bash
pip install openai==1.71.0 pandas==2.1.4 tqdm
```

3. **Configure API endpoints**:
   - Update the `api_key` and `base_url` in the respective Python files
   - Ensure VLLM services are running and accessible

## Usage

### 1. Report Structuring
Convert raw MRI reports to structured format:

```bash
python finding_structure.py --json_path /path/to/reports.json --language english
```

**Parameters**:
- `--json_path`: Path to input JSON file containing medical reports
- `--language`: Processing language (`chinese` or `english`)

### 2. Diagnostic Inference
Generate diagnostic conclusions from findings:

```bash
python diagnosis_from_findings.py \
    --json_path /path/to/reports.json \
    --model deepseek-reasoner \
    --prompt_type top1 \
    --language chinese \
    --mode struct \
    --max_workers 5
```

**Parameters**:
- `--json_path`: Input JSON file path
- `--model`: AI model selection (deepseek-reasoner, qwen3_235b_2507, etc.)
- `--prompt_type`: Diagnostic approach (`top1`, `top3`, `free`)
- `--language`: Processing language (`chinese`, `english`)
- `--mode`: Input type (`struct` for structured, `direct` for original)
- `--add_clinical_info`: Include clinical information (optional)
- `--max_workers`: Concurrent processing threads

### 3. Supported Models
The system supports multiple state-of-the-art language models:
- `deepseek-reasoner`
- `qwen3_235b_2507`
- `gpt_oss_120b`
- `llama3.3_70b`
- `DeepSeek_Distill_Qwen32B`
- `gpt_oss_20b`
- `Baichuan_M1`
- `wingpt_gemma2_9b`
- `llama3.1_8b`
- And more...

## Input Data Format

The system expects JSON files with the following structure:

```json
[
  {
    "FID": "unique_identifier",
    "patient_id": "patient_123",
    "检查时间": "2024-01-01",
    "性别": "Male",
    "年龄": 65,
    "临床诊断": "Clinical diagnosis",
    "检查项目": "Brain MRI",
    "原_检查所见": "Original findings text...",
    "原_检查结论": "Original conclusion text...",
    "临床信息汇总": "Clinical information summary...",
    "标签": "Disease label",
    "标准化结论": ["Standardized conclusions"]
  }
]
```

## Output Structure

### Structured Reports
- **Individual JSON files**: Detailed processing results for each report
- **Excel summaries**: Consolidated results for analysis
- **Reasoning traces**: Complete AI reasoning process for transparency

### Diagnostic Results
- **Inference conclusions**: AI-generated diagnostic opinions
- **Confidence scoring**: Multiple diagnosis options with rankings
- **Clinical correlation**: Integration of findings with clinical context

## Disease Classification

The system uses a standardized 16-category disease classification:

1. Normal
2. White-matter hyperintensities
3. Cerebral atrophy
4. Acute/subacute cerebral infarction
5. Encephalomalacia
6. Cerebral hemorrhage
7. Brain contusion
8. Subdural/epidural hematoma
9. Subdural effusion
10. Cavernous angioma
11. Arachnoid cyst
12. Tumor (with subtype specification)
13. Subarachnoid hemorrhage
14. Brain abscess
15. Encephalitis
16. Inflammatory demyelination

## Performance Considerations

- **Concurrent Processing**: Multi-threaded execution for improved throughput
- **Retry Mechanisms**: Automatic retry for failed API calls
- **Resume Capability**: Skip already processed files for interrupted runs
- **Memory Management**: Efficient handling of large datasets

## Citation

If you use this code in your research, please cite:

```bibtex
@article{your_paper_2024,
  title={Evaluation of Large Language Models for Automated Diagnosis in Brain MRI Reporting: A Multicenter Benchmark and Reader Study},
  author={[Author Names]},
  journal={[Journal Name]},
  year={2024}
}
```

## License

This project is licensed under the MIT License.

Copyright (c) 2024 [Author Names]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
