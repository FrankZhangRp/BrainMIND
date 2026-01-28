import os
import json
import pandas as pd
from openai import OpenAI
import concurrent.futures
import time
from tqdm import tqdm
from prompt import SYSTEM_PROMPT_FINDINGS_CHINESE, SYSTEM_PROMPT_FINDINGS_ENGLISH
import argparse

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

removed_case_list = []


def extract_report_sections(result):
    """
    Extract structured findings section from the AI-generated report result.

    Args:
        result (str): The raw output from the AI model containing findings section

    Returns:
        dict: A dictionary containing:
            - cleaned_findings: Extracted findings section
            - findings_parts: Parsed subsections of findings (overview, disease-specific findings, etc.)
    """
    try:
        findings_start = result.find("<findings>") + len("<findings>")
        findings_end = result.find("</findings>")

        if findings_start == -1 or findings_end == -1:
            raise ValueError("Could not find <findings> tags in the result")

        cleaned_findings = result[findings_start:findings_end].strip()

        findings_parts = {}

        overview_start = cleaned_findings.find("Overall Findings Summary:")
        if overview_start == -1:
            overview_start = cleaned_findings.find("整体所见概要:")

        if overview_start != -1:
            next_section = cleaned_findings.find("Findings Corresponding to Each Disease:")
            if next_section == -1:
                next_section = cleaned_findings.find("各疾病对应所见:")

            if next_section != -1:
                if "Overall Findings Summary:" in cleaned_findings:
                    overview = cleaned_findings[overview_start + len("Overall Findings Summary:"):next_section].strip()
                else:
                    overview = cleaned_findings[overview_start + len("整体所见概要:"):next_section].strip()
                findings_parts['overall_summary'] = overview

        diseases_start = cleaned_findings.find("Findings Corresponding to Each Disease:")
        if diseases_start == -1:
            diseases_start = cleaned_findings.find("各疾病对应所见:")

        if diseases_start != -1:
            detailed_start = cleaned_findings.find("Detailed Imaging Findings:")
            if detailed_start == -1:
                detailed_start = cleaned_findings.find("详细影像学发现:")

            if detailed_start != -1:
                if "Findings Corresponding to Each Disease:" in cleaned_findings:
                    diseases_section = cleaned_findings[diseases_start + len("Findings Corresponding to Each Disease:"):detailed_start].strip()
                else:
                    diseases_section = cleaned_findings[diseases_start + len("各疾病对应所见:"):detailed_start].strip()
                findings_parts['disease_specific_findings'] = diseases_section

                if "Detailed Imaging Findings:" in cleaned_findings:
                    detailed_section = cleaned_findings[detailed_start + len("Detailed Imaging Findings:"):].strip()
                else:
                    detailed_section = cleaned_findings[detailed_start + len("详细影像学发现:"):].strip()
                findings_parts['detailed_findings'] = detailed_section
            else:
                if "Findings Corresponding to Each Disease:" in cleaned_findings:
                    diseases_section = cleaned_findings[diseases_start + len("Findings Corresponding to Each Disease:"):].strip()
                else:
                    diseases_section = cleaned_findings[diseases_start + len("各疾病对应所见:"):].strip()
                findings_parts['disease_specific_findings'] = diseases_section

        return {
            'cleaned_findings': cleaned_findings,
            'findings_parts': findings_parts
        }

    except Exception as e:
        print(f"Error extracting report sections: {str(e)}")
        return {
            'cleaned_findings': '',
            'findings_parts': {}
        }


def process_findings_stage(client, original_findings, language='english'):
    """
    Process the findings using the appropriate language-specific prompt.

    Args:
        client (OpenAI): The OpenAI client instance
        original_findings (str): The original findings text to be processed
        language (str): Language for processing ('chinese' or 'english')

    Returns:
        str: The processed findings from the AI model, or None if error occurs
    """
    if language.lower() == 'chinese':
        system_prompt = SYSTEM_PROMPT_FINDINGS_CHINESE
    else:
        system_prompt = SYSTEM_PROMPT_FINDINGS_ENGLISH

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"""
Findings: {original_findings}
"""}
    ]

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.6,
            max_tokens=2048,
            stream=False
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"Error in findings stage: {str(e)}")
        return None


def process_single_report(client, findings, disease_type, language='english'):
    """
    Process a single medical report by processing only the findings.

    Args:
        client (OpenAI): The OpenAI client instance
        findings (str): The original findings section
        disease_type (str): The disease type/label for this report
        language (str): Language for processing ('chinese' or 'english')

    Returns:
        str: The processed report result from the AI model
    """
    findings_result = process_findings_stage(client, findings, language)

    return findings_result


def clean_reports(json_path, language='english'):
    """
    Main function to clean and structure medical reports from a JSON file.

    Args:
        json_path (str): Path to the input JSON file containing medical reports
        language (str): Language for processing ('chinese' or 'english')
    """
    client = OpenAI(
        api_key="put your api key here",
        base_url="put your base url here"
    )

    with open(json_path, 'r', encoding='utf-8') as f:
        reports = json.load(f)

    json_filename = os.path.splitext(os.path.basename(json_path))[0]
    output_base_dir = f'{ROOT_DIR}/structure/cleaned_by_deepseekv3/{json_filename}'

    excel_data = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = []

        for report in reports:
            future = executor.submit(
                process_single_report,
                client,
                report['original_findings'],
                report['label'],
                language
            )
            futures.append((future, report))

        for future, report in tqdm(futures, desc="Processing medical reports", total=len(futures)):
            try:
                findings_result = future.result()

                if findings_result:
                    extracted_data = extract_report_sections(findings_result)
                    cleaned_findings = extracted_data['cleaned_findings']
                    findings_parts = extracted_data['findings_parts']

                    output_file = f'{output_base_dir}/json_result/{report["FID"]}.json'
                    os.makedirs(f'{output_base_dir}/json_result', exist_ok=True)

                    report_data = {
                        'FID': report["FID"],
                        'examination_date': report['examination_date'],
                        'gender': report['gender'],
                        'age': report['age'],
                        'clinical_diagnosis': report['clinical_diagnosis'],
                        'examination_type': report['examination_type'],
                        'original_findings': report['original_findings'],
                        'structured_findings': cleaned_findings,
                        'overall_summary': findings_parts.get('overall_summary', ''),
                        'disease_specific_findings': findings_parts.get('disease_specific_findings', ''),
                        'detailed_findings': findings_parts.get('detailed_findings', ''),
                        'label': report['label'],
                        'structuring_raw_output': findings_result
                    }

                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(report_data, f, ensure_ascii=False, indent=2)

                    excel_data.append({
                        'FID': report["FID"],
                        'examination_date': report['examination_date'],
                        'gender': report['gender'],
                        'age': report['age'],
                        'clinical_diagnosis': report['clinical_diagnosis'],
                        'examination_type': report['examination_type'],
                        'original_findings': report['original_findings'],
                        'structured_findings': cleaned_findings,
                        'overall_summary': findings_parts.get('overall_summary', ''),
                        'disease_specific_findings': findings_parts.get('disease_specific_findings', ''),
                        'detailed_findings': findings_parts.get('detailed_findings', ''),
                        'label': report['label']
                    })

            except Exception as e:
                print(f"Error processing report {report['FID']}: {str(e)}")

    if excel_data:
        df = pd.DataFrame(excel_data)
        os.makedirs(output_base_dir, exist_ok=True)
        excel_output_path = f'{output_base_dir}/cleaned_reports.xlsx'
        df.to_excel(excel_output_path, index=False)
        print(f"Excel file saved to: {excel_output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Clean and structure medical reports using DeepSeek AI API'
    )
    parser.add_argument(
        '--json_path',
        type=str,
        required=True,
        help='Path to the input JSON file containing medical reports'
    )
    parser.add_argument(
        '--language',
        type=str,
        default='english',
        choices=['chinese', 'english'],
        help='Language for processing (chinese or english). Default: english'
    )

    args = parser.parse_args()
    clean_reports(args.json_path, args.language)
