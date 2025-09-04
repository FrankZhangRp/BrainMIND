import os
import json
import pandas as pd
import argparse
from openai import OpenAI
import concurrent.futures
import time
from tqdm import tqdm
from prompt import (
    FINDINGS_TO_CONCLUSION_PROMPT_TOP1_CHINESE,
    FINDINGS_TO_CONCLUSION_PROMPT_TOP3_CHINESE,
    FINDINGS_TO_CONCLUSION_PROMPT_FREE_CHINESE,
    FINDINGS_TO_CONCLUSION_PROMPT_TOP1_ENGLISH,
    FINDINGS_TO_CONCLUSION_PROMPT_TOP3_ENGLISH,
    FINDINGS_TO_CONCLUSION_PROMPT_FREE_ENGLISH
)

# Define the root directory for the project
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def extract_report_sections(result, mode='direct'):
    """
    Extract reasoning and conclusion sections from the AI-generated report result.
    
    Args:
        result (str): The raw output from the AI model containing thinking and conclusion sections
        mode (str): Processing mode ('direct' or 'struct')
        
    Returns:
        dict: A dictionary containing:
            - cleaned_reasoning: Extracted reasoning/thinking process
            - cleaned_conclusion: List of extracted conclusions
    """
    try:
        # Find thinking section boundaries
        reasoning_start_pos = result.find("<think>")
        reasoning_start = (reasoning_start_pos + len("<think>")) if reasoning_start_pos != -1 else 0
        
        reasoning_end = result.rfind("</think>")
        
        # Find conclusion section boundaries
        conclusion_start = result.rfind("<conclusion>") + len("<conclusion>")
        conclusion_end = result.rfind("</conclusion>")
        
        # Extract and clean reasoning section
        cleaned_reasoning = result[reasoning_start:reasoning_end].strip()
        
        # Extract and clean conclusion section, split by lines and filter empty ones
        cleaned_conclusion = [
            c.strip() for c in result[conclusion_start:conclusion_end].strip().split('\n') 
            if c.strip()
        ]
        
        return {
            'cleaned_reasoning': cleaned_reasoning,
            'cleaned_conclusion': cleaned_conclusion
        }

    except Exception as e:
        print(f"Error extracting report sections: {str(e)}")
        return {
            'cleaned_reasoning': '',
            'cleaned_conclusion': []
        }


def get_prompt_by_type_and_language(prompt_type, language):
    """
    Select the appropriate prompt based on prompt type and language.
    
    Args:
        prompt_type (str): Type of prompt ('top1', 'top3', 'free')
        language (str): Language for the prompt ('chinese' or 'english')
        
    Returns:
        str: The selected prompt text
        
    Raises:
        ValueError: If unsupported prompt type or language combination
    """
    prompt_mapping = {
        ('top1', 'chinese'): FINDINGS_TO_CONCLUSION_PROMPT_TOP1_CHINESE,
        ('top3', 'chinese'): FINDINGS_TO_CONCLUSION_PROMPT_TOP3_CHINESE,
        ('free', 'chinese'): FINDINGS_TO_CONCLUSION_PROMPT_FREE_CHINESE,
        ('top1', 'english'): FINDINGS_TO_CONCLUSION_PROMPT_TOP1_ENGLISH,
        ('top3', 'english'): FINDINGS_TO_CONCLUSION_PROMPT_TOP3_ENGLISH,
        ('free', 'english'): FINDINGS_TO_CONCLUSION_PROMPT_FREE_ENGLISH,
    }
    
    key = (prompt_type, language)
    if key not in prompt_mapping:
        raise ValueError(f"Unsupported prompt type '{prompt_type}' with language '{language}'")
    
    return prompt_mapping[key]


def process_single_report(args, client, findings, mode='direct'):
    """
    Process a single medical report to generate diagnostic conclusions from findings.
    
    Args:
        args: Command line arguments containing model configuration
        client (OpenAI): The OpenAI-compatible client instance
        findings (str or list): The medical findings text to be processed
        mode (str): Processing mode ('direct' or 'struct')
        
    Returns:
        str: The AI-generated response containing reasoning and conclusions, or None if failed
    """
    # Convert findings list to string if needed
    if isinstance(findings, list):
        findings = '\n'.join(findings)
    
    # Select appropriate prompt based on type and language
    prompt = get_prompt_by_type_and_language(args.prompt_type, args.language)
    
    # Prepare user input template based on language
    if args.language == 'chinese':
        user_content = f"患者的检查所见如下所示: {findings}\n\n请严格按模板作答，从下面一行开始：\n<think>\n"
    else:  # english
        user_content = f"The patient's findings are as follows: {findings}\n\nPlease answer strictly according to the template, starting from the line below:\n<think>\n"
    
    # Prepare messages for the AI model
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_content}
    ]
    
    # Retry mechanism for robust API calls
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Configure API call parameters based on model type
            if args.model == 'Baichuan_M1':
                response = client.chat.completions.create(
                    model=args.model,
                    messages=messages,
                    temperature=0.6,
                    max_tokens=4096,
                    stream=False,
                    stop=[],                    # Ensure no implicit stop tokens
                    logit_bias={"151645": -100} # Suppress <|im_end|> token
                )
            elif 'deepseek' in args.model:
                response = client.chat.completions.create(
                    model=args.model,
                    messages=messages,
                    temperature=0.6,
                    max_tokens=8192,
                    stream=False
                )
            elif 'qwen3' in args.model:
                response = client.chat.completions.create(
                    model=args.model,
                    messages=messages,
                    max_tokens=8192,
                    stream=False,
                    stop=["</conclusion>"],
                    logit_bias={"151645": -100},
                    extra_body={"bad_words": ["<tool_call", "</tool_call", "<function_call"]}
                )
            else:
                # Default configuration for other models
                response = client.chat.completions.create(
                    model=args.model,
                    messages=messages,
                    max_tokens=8192,
                    stream=False
                )
            
            # Check if response is valid
            if response and response.choices:
                return response.choices[0].message.content
            else:
                print(f"Empty response received from API, attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retry
                    continue
                else:
                    return None
                    
        except Exception as e:
            print(f"Error in processing report (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(1)  # Wait before retry
                continue
            else:
                return None
    
    return None


def clean_reports(args, mode='direct', max_workers=5):
    """
    Main function to process medical reports and generate diagnostic conclusions.
    
    Args:
        args: Command line arguments containing configuration
        mode (str): Processing mode ('direct' for original findings, 'struct' for structured findings)
        max_workers (int): Maximum number of concurrent workers for parallel processing
    """
    # Initialize OpenAI-compatible client
    # Note: Replace with your actual API key and base URL
    client = OpenAI(
        api_key="your-api-key-here",  # Replace with your API key
        base_url="https://your-api-endpoint.com"  # Replace with your API base URL
    )
    
    # Load medical reports data from JSON file
    with open(args.json_path, 'r', encoding='utf-8') as f:
        reports = json.load(f)
    
    # Extract filename for directory naming
    json_filename = os.path.splitext(os.path.basename(args.json_path))[0]
    
    # Initialize list to store data for Excel export
    excel_data = []
    
    # Process reports concurrently for better performance
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        
        # Submit processing tasks for each report
        for report in reports:
            # Construct output file path
            output_file = f'{ROOT_DIR}/results_{args.prompt_type}_{json_filename}/{args.model}_{args.mode}_clinical_info_{args.add_clinical_info}_{args.language}/{report["patient_id"]}.json'
            
            # Skip if file already exists (resume functionality)
            if os.path.exists(output_file):
                continue
            
            # Prepare findings based on processing mode
            if mode == 'direct':
                findings = report['原_检查所见']  # Original findings
            elif mode == 'struct':
                findings = report.get('结构化检查所见', [])  # Structured findings
            
            # Add clinical information if requested
            if args.add_clinical_info:
                clinical_info = report['临床信息汇总']
                if args.language == 'chinese':
                    findings = f'患者的补充临床信息汇总如下{clinical_info}\n患者的检查所见如下{findings}'
                else:  # english
                    findings = f'Additional clinical information summary: {clinical_info}\nPatient findings: {findings}'
            
            # Submit processing task to thread pool
            future = executor.submit(
                process_single_report,
                args,
                client,
                findings,
                mode
            )
            futures.append((future, report))
        
        # Process results with progress bar
        for future, report in tqdm(futures, desc="Processing medical reports", total=len(futures)):
            try:
                # Get processing result
                result = future.result()
                
                if result:
                    # Extract structured sections from AI response
                    extracted_data = extract_report_sections(result, mode)
                    cleaned_reasoning = extracted_data['cleaned_reasoning']
                    cleaned_conclusion = extracted_data['cleaned_conclusion']
                    
                    # Determine input findings based on mode
                    findings_input = []
                    if mode == 'direct':
                        findings_input = report['原_检查所见']
                    elif mode == 'struct':
                        findings_input = report.get('结构化检查所见', [])
                    
                    # Create output directory
                    output_dir = f'{ROOT_DIR}/results_{args.prompt_type}_{json_filename}/{args.model}_{args.mode}_clinical_info_{args.add_clinical_info}_{args.language}'
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # Save individual report as JSON file
                    output_file = f'{output_dir}/{report["patient_id"]}.json'
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            'patient_id': report["patient_id"],
                            '性别': report['性别'],                # Gender
                            '年龄': report['年龄'],                # Age
                            '输入检查所见': findings_input,         # Input findings
                            '推理过程': cleaned_reasoning,          # Reasoning process
                            '推理诊断结论': cleaned_conclusion,     # Inferred diagnostic conclusions
                            'label_conclusion': report['标准化结论'], # Standardized conclusion labels
                            'full_response': result,              # Full AI response
                        }, f, ensure_ascii=False, indent=2)
                    
                    # Add to Excel data collection
                    excel_data.append({
                        'patient_id': report["patient_id"],
                        '性别': report['性别'],
                        '年龄': report['年龄'],
                        '输入检查所见': findings_input,
                        '推理过程': cleaned_reasoning,
                        '推理诊断结论': cleaned_conclusion,
                        'label_conclusion': report['标准化结论'],
                        'full_response': result,
                    })
                    
            except Exception as e:
                print(f"Error processing report {report['patient_id']}: {str(e)}")
    
    # Save consolidated Excel file
    if excel_data:
        df = pd.DataFrame(excel_data)
        
        # Create output directory for Excel file
        excel_output_dir = f'{ROOT_DIR}/results_{args.prompt_type}_{json_filename}'
        os.makedirs(excel_output_dir, exist_ok=True)
        
        # Generate output filename with configuration details
        output_filename = f'reasoning_inference_results_{args.model}_{args.mode}_clinical_info_{args.add_clinical_info}_{args.language}.xlsx'
        excel_path = f'{excel_output_dir}/{output_filename}'
        
        # Save Excel file
        df.to_excel(excel_path, index=False)
        print(f"Results saved to Excel file: {excel_path}")


if __name__ == "__main__":
    # Set up command line argument parser
    parser = argparse.ArgumentParser(description="Process medical reports to generate diagnostic conclusions from findings")
    
    parser.add_argument('--mode', type=str, choices=['struct', 'direct'], 
                       default='struct', 
                       help='Type of findings to use for inference: struct (structured) or direct (original)')
    
    parser.add_argument('--add_clinical_info', action='store_true',
                       help='Whether to add clinical information to the findings input')
    
    parser.add_argument('--json_path', type=str, required=True,
                       help='Path to the input JSON file containing medical reports')
    
    parser.add_argument('--model', type=str, default='deepseek-reasoner', 
                       choices=['llama3.1_8b', 'wingpt2_gemma2_9b', 'llama3.3_70b', 'DeepSeek_Distill_Qwen32B', 'deepseek-reasoner', 'gpt_oss_120b', 'gpt_oss_20b', 'Baichuan_M1', 'qwen3_235b_2507'],
                       help='AI model to use for inference')
    
    parser.add_argument('--max_workers', type=int, default=5,
                       help='Maximum number of concurrent workers for parallel processing')
    
    parser.add_argument('--prompt_type', type=str, choices=['top1', 'top3', 'free'], 
                       default='top1', 
                       help='Type of prompt to use: top1 (single diagnosis), top3 (up to 3 diagnoses), free (unconstrained)')
    
    parser.add_argument('--language', type=str, choices=['chinese', 'english'], 
                       default='chinese', 
                       help='Language of the prompt and processing')
    
    # Parse arguments and run main function
    args = parser.parse_args()
    clean_reports(args, args.mode, args.max_workers)
