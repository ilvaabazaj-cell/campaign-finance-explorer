def sample_huge_file(input_path, output_path, num_lines=1000):
    print(f"Reading from: {input_path}...")
    try:
        with open(input_path, 'r', encoding='utf-8', errors='ignore') as infile:
            with open(output_path, 'w', encoding='utf-8') as outfile:
                for i in range(num_lines):
                    line = infile.readline()
                    if not line:
                        break  # Reached the end of the file early
                    outfile.write(line)
        print(f"Successfully wrote {i+1} rows to: {output_path}\n")
    except FileNotFoundError:
        print(f"Error: Could not find the file at {input_path}. Check your path!\n")

if __name__ == "__main__":
    # Using the absolute paths to your OneDrive Desktop folder
    raw_indiv_path = r"C:\Users\io\OneDrive\Desktop\UNITRENTO\1st YEAR\2nd semester\Big Data Technologies\Project\Bulk download\itcont.txt"
    raw_pas2_path = r"C:\Users\io\OneDrive\Desktop\UNITRENTO\1st YEAR\2nd semester\Big Data Technologies\Project\Bulk download\itpas2.txt"
    raw_oth_path = r"C:\Users\io\OneDrive\Desktop\UNITRENTO\1st YEAR\2nd semester\Big Data Technologies\Project\Bulk download\itoth.txt"

    # Destination inside your active project folder
    sample_indiv_dest = "data_seed/indiv_sample.txt"
    sample_pas2_dest = "data_seed/pas2_sample.txt"
    sample_oth_dest = "data_seed/oth_sample.txt"

    # Run the sampling
    sample_huge_file(raw_indiv_path, sample_indiv_dest, num_lines=10000)
    sample_huge_file(raw_pas2_path, sample_pas2_dest, num_lines=10000)
    sample_huge_file(raw_oth_path, sample_oth_dest, num_lines=10000)