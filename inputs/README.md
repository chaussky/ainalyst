# inputs/: Input materials for analysis

This is where the BA drops any files that need to be processed as part of business analysis.

## What you can put here

- **Interview transcripts**: records of conversations with stakeholders
- **Workshop and facilitated-session transcripts**: results of group meetings
- **Business rules and policies**: the company's internal policies
- **Regulatory and regulator requirements**: external constraints
- **Technical specifications**: existing documentation for the systems
- **Survey and questionnaire results**: answers from forms
- **Other documents**: any source that contains requirements or context

## Supported formats

`.txt`, `.md`, `.pdf`, `.docx`

## How to use

Put a file in this folder and tell Claude:

> "Process this material: inputs/FILENAME"

Or in the context of a specific BABOK task:

> "Run task 4.2 based on the file inputs/workshop_results.txt"

## Note

This folder is not committed to Git (excluded via .gitignore); the files may contain
confidential data. The folder structure is preserved via `.gitkeep`.
