"""Generate GitHub Pages reports from precomputed event descriptor CSVs."""

import os

import csv_lib
import html_lib


def main():
    """Main execution function - process all seasons and generate pages"""
    import shutil
    print("[*] OOFS Stats Page Generator\n")
    print("=" * 60)


    generated_csvs = csv_lib.generate_event_csvs()
    print(f"  Generated {len(generated_csvs)} event descriptor CSVs")
    
    # Create top-level docs folder
    os.makedirs('docs', exist_ok=True)

    # NEW: Copy the CSS file into the docs folder so GitHub Pages can see it
    try:
        shutil.copy(os.path.join(html_lib.TEMPLATES_DIR, 'styles.css'), os.path.join('docs', 'styles.css'))
        print("  Copied styles.css to docs/")
    except FileNotFoundError:
        print("  WARNING: templates/styles.css not found!")

    # Loop through all configured seasons
    for season_id, season_info in csv_lib.SEASONS.items():
        print(f"\n[Season] Processing {season_info['name']}...")
        season_config = {
            section_name: {
                f'{os.path.splitext(filename)[0]}.csv': race_info
                for filename, race_info in events.items()
            }
            for section_name, events in csv_lib.load_season_config(season_id).items()
            if section_name != csv_lib.SEASON_INFO_KEY
        }
        
        # Create season-specific output folder
        season_output_dir = os.path.join('docs', season_id)
        os.makedirs(season_output_dir, exist_ok=True)
        
        has_split_sprint_classes = csv_lib.season_has_sprint_class_data(season_id)

        # ===== SPRINT RACE PACE =====
        if not has_split_sprint_classes:
            print("  [Sprint] Race Pace...")
            sprint_race_dfs = {}
            xml_folder = os.path.join('assets', 'csv', season_id, 'sprint')
            
            for filename, race_info in season_config['sprint_races'].items():
                xml_path = os.path.join(xml_folder, filename)
                if os.path.exists(xml_path):
                    df = csv_lib.load_event_csv(xml_path)
                    if df is not None:
                        sprint_race_dfs[race_info['name']] = df
                else:
                    print(f"    Not found: {xml_path}")
            
            print(f"    DEBUG: After loading, sprint_race_dfs={list(sprint_race_dfs.keys()) if sprint_race_dfs else 'EMPTY'}")
            
            if sprint_race_dfs:
                print(f"    DEBUG: sprint_race_dfs has {len(sprint_race_dfs)} entries: {list(sprint_race_dfs.keys())}")
                race_codes, track_names, code_to_track = csv_lib.load_races_dynamically(season_config['sprint_races'], xml_folder)
                print(f"    DEBUG: race_codes={race_codes}, code_to_track={code_to_track}")
                comparison_df, _, avg_pace_cols, used_race_codes, track_names = csv_lib.process_races_into_comparison_df(sprint_race_dfs, race_codes, code_to_track, season_id, 'sprint')
                
                if comparison_df is not None:
                    html_content = html_lib.generate_comparison_page(
                        comparison_df, avg_pace_cols, used_race_codes, track_names,
                        'Sprint Race Data', 'sprint_race.html', season_id,
                        'Sprint Race Pace Trend', 'Race Pace % (vs Alien)', mode='race',
                    )
                    
                    output_file = os.path.join(season_output_dir, 'sprint_race.html')
                    with open(output_file, 'w', encoding='utf-8-sig') as f:
                        f.write(html_content)
                    if season_id == list(csv_lib.SEASONS.keys())[0]:  # Create index.html for first season
                        with open(os.path.join(season_output_dir, 'index.html'), 'w', encoding='utf-8-sig') as f:
                            f.write(html_content)
                    print("    Generated sprint_race.html")
                else:
                    print("    Comparison DF is None for sprint races")
            else:
                print("    No sprint race data found")
        else:
            print("  [Sprint] Skipping aggregate race pace page because split sprint classes are present")
            output_file = os.path.join(season_output_dir, 'sprint_race.html')
            if os.path.exists(output_file):
                os.remove(output_file)
        
            # ===== SPRINT LMP3 RACE PACE (Class-filtered) =====
            print("  [Sprint] LMP3 Race Pace...")
            sprint_lmp3_race_dfs = {}
            xml_folder = os.path.join('assets', 'csv', season_id, 'sprint')
            
            for filename, race_info in season_config['sprint_races'].items():
                xml_path = os.path.join(xml_folder, filename)
                if os.path.exists(xml_path):
                    df = csv_lib.load_event_csv(xml_path, 'LMP3')
                    if df is not None:
                        sprint_lmp3_race_dfs[race_info['name']] = df
                else:
                    print(f"    Not found: {xml_path}")
            
            if sprint_lmp3_race_dfs:
                race_codes, track_names, code_to_track = csv_lib.load_races_dynamically(season_config['sprint_races'], xml_folder)
                comparison_df, _, avg_pace_cols, used_race_codes, track_names = csv_lib.process_races_into_comparison_df(sprint_lmp3_race_dfs, race_codes, code_to_track, season_id, 'sprint', 'LMP3')
                
                if comparison_df is not None:
                    html_content = html_lib.generate_comparison_page(
                        comparison_df, avg_pace_cols, used_race_codes, track_names,
                        'Sprint LMP3 Race Data', 'sprint_lmp3_race.html', season_id,
                        'Sprint LMP3 Race Pace Trend', 'Race Pace % (vs Alien)', mode='race',
                    )
                    
                    with open(os.path.join(season_output_dir, 'sprint_lmp3_race.html'), 'w', encoding='utf-8-sig') as f:
                        f.write(html_content)
                    print("    Generated sprint_lmp3_race.html")
                else:
                    print("    Comparison DF is None for LMP3 races")
            else:
                print("    No LMP3 sprint race data found")
            
            # ===== SPRINT GT3 RACE PACE (Class-filtered) =====
            print("  [Sprint] GT3 Race Pace...")
            sprint_gt3_race_dfs = {}
            
            for filename, race_info in season_config['sprint_races'].items():
                xml_path = os.path.join(xml_folder, filename)
                print(f"    DEBUG: Processing GT3 race CSV: {xml_path}")
                if os.path.exists(xml_path):
                    df = csv_lib.load_event_csv(xml_path, 'GT3')
                    if df is not None:
                        sprint_gt3_race_dfs[race_info['name']] = df
                else:
                    print(f"    Not found: {xml_path}")
            
            if sprint_gt3_race_dfs:
                race_codes, track_names, code_to_track = csv_lib.load_races_dynamically(season_config['sprint_races'], xml_folder)
                comparison_df, _, avg_pace_cols, used_race_codes, track_names = csv_lib.process_races_into_comparison_df(sprint_gt3_race_dfs, race_codes, code_to_track, season_id, 'sprint', 'GT3')
                
                if comparison_df is not None:
                    html_content = html_lib.generate_comparison_page(
                        comparison_df, avg_pace_cols, used_race_codes, track_names,
                        'Sprint GT3 Race Data', 'sprint_gt3_race.html', season_id,
                        'Sprint GT3 Race Pace Trend', 'Race Pace % (vs Alien)', mode='race',
                    )
                    
                    with open(os.path.join(season_output_dir, 'sprint_gt3_race.html'), 'w', encoding='utf-8-sig') as f:
                        f.write(html_content)
                    print("    Generated sprint_gt3_race.html")
                else:
                    print("    Comparison DF is None for GT3 races")
            else:
                print("    No GT3 sprint race data found")
        
        # ===== SPRINT QUALI PACE =====
        if not has_split_sprint_classes:
            print("  [Sprint] Quali Pace...")
            sprint_quali_dfs = {}
            
            for filename, quali_info in season_config['sprint_qualis'].items():
                xml_path = os.path.join(xml_folder, filename)
                if os.path.exists(xml_path):
                    df = csv_lib.load_event_csv(xml_path)
                    if df is not None:
                        sprint_quali_dfs[quali_info['name']] = df
            
            if sprint_quali_dfs:
                race_codes, track_names, code_to_track = csv_lib.load_races_dynamically(season_config['sprint_qualis'], xml_folder)
                comparison_df, _, avg_pace_cols, used_race_codes, track_names = csv_lib.process_races_into_comparison_df(sprint_quali_dfs, race_codes, code_to_track, season_id, 'sprint')
                
                if comparison_df is not None:
                    html_content = html_lib.generate_comparison_page(
                        comparison_df, avg_pace_cols, used_race_codes, track_names,
                        'Sprint Quali Data', 'sprint_quali.html', season_id,
                        'Sprint Quali Pace Trend', 'Quali Pace % (vs Alien)', mode='quali',
                    )
                    
                    with open(os.path.join(season_output_dir, 'sprint_quali.html'), 'w', encoding='utf-8-sig') as f:
                        f.write(html_content)
                    print("    Generated sprint_quali.html")
            else:
                print("    No sprint quali data found")
        else:
            print("  [Sprint] Skipping aggregate quali page because split sprint classes are present")
            output_file = os.path.join(season_output_dir, 'sprint_quali.html')
            if os.path.exists(output_file):
                os.remove(output_file)
        
            # ===== SPRINT LMP3 QUALI PACE (Class-filtered) =====
            print("  [Sprint] LMP3 Quali Pace...")
            sprint_lmp3_quali_dfs = {}
            
            for filename, quali_info in season_config['sprint_qualis'].items():
                xml_path = os.path.join(xml_folder, filename)
                if os.path.exists(xml_path):
                    df = csv_lib.load_event_csv(xml_path, 'LMP3')
                    if df is not None:
                        sprint_lmp3_quali_dfs[quali_info['name']] = df
                else:
                    print(f"    Not found: {xml_path}")
            
            if sprint_lmp3_quali_dfs:
                race_codes, track_names, code_to_track = csv_lib.load_races_dynamically(season_config['sprint_qualis'], xml_folder)
                comparison_df, _, avg_pace_cols, used_race_codes, track_names = csv_lib.process_races_into_comparison_df(sprint_lmp3_quali_dfs, race_codes, code_to_track, season_id, 'sprint', 'LMP3')
                
                if comparison_df is not None:
                    html_content = html_lib.generate_comparison_page(
                        comparison_df, avg_pace_cols, used_race_codes, track_names,
                        'Sprint LMP3 Quali Data', 'sprint_lmp3_quali.html', season_id,
                        'Sprint LMP3 Quali Pace Trend', 'Quali Pace % (vs Alien)', mode='quali',
                    )
                    
                    with open(os.path.join(season_output_dir, 'sprint_lmp3_quali.html'), 'w', encoding='utf-8-sig') as f:
                        f.write(html_content)
                    print("    Generated sprint_lmp3_quali.html")
                else:
                    print("    Comparison DF is None for LMP3 qualies")
            else:
                print("    No LMP3 sprint quali data found")
            
            # ===== SPRINT GT3 QUALI PACE (Class-filtered) =====
            print("  [Sprint] GT3 Quali Pace...")
            sprint_gt3_quali_dfs = {}
            
            for filename, quali_info in season_config['sprint_qualis'].items():
                xml_path = os.path.join(xml_folder, filename)
                if os.path.exists(xml_path):
                    df = csv_lib.load_event_csv(xml_path, 'GT3')
                    if df is not None:
                        sprint_gt3_quali_dfs[quali_info['name']] = df
                else:
                    print(f"    Not found: {xml_path}")
            
            if sprint_gt3_quali_dfs:
                race_codes, track_names, code_to_track = csv_lib.load_races_dynamically(season_config['sprint_qualis'], xml_folder)
                comparison_df, _, avg_pace_cols, used_race_codes, track_names = csv_lib.process_races_into_comparison_df(sprint_gt3_quali_dfs, race_codes, code_to_track, season_id, 'sprint', 'GT3')
                
                if comparison_df is not None:
                    html_content = html_lib.generate_comparison_page(
                        comparison_df, avg_pace_cols, used_race_codes, track_names,
                        'Sprint GT3 Quali Data', 'sprint_gt3_quali.html', season_id,
                        'Sprint GT3 Quali Pace Trend', 'Quali Pace % (vs Alien)', mode='quali',
                    )
                    
                    with open(os.path.join(season_output_dir, 'sprint_gt3_quali.html'), 'w', encoding='utf-8-sig') as f:
                        f.write(html_content)
                    print("    Generated sprint_gt3_quali.html")
                else:
                    print("    Comparison DF is None for GT3 qualies")
            else:
                print("    No GT3 sprint quali data found")
        
        # ===== MULTICLASS PROTOTYPE RACE PACE =====
        prototype_class = csv_lib.get_multiclass_prototype_class(season_id)
        championship_name = csv_lib.get_multiclass_championship_name(season_id)
        prototype_filter = 'P2UR' if prototype_class == 'P2UR' else 'Hyper'
        print(f"  [{championship_name}] {prototype_class}/GT3 Race Pace...")
        mc_p2ur_race_dfs = {}
        xml_folder_mc = os.path.join('assets', 'csv', season_id, 'multiclass')
        
        for filename, mc_info in season_config['multiclass_races'].items():
            xml_path = os.path.join(xml_folder_mc, filename)
            if os.path.exists(xml_path):
                df = csv_lib.load_event_csv(xml_path, prototype_filter)
                if df is not None:
                    mc_p2ur_race_dfs[mc_info['name']] = df
            else:
                print(f"    Not found: {xml_path}")
        
        if mc_p2ur_race_dfs:
            race_codes, track_names, code_to_track = csv_lib.load_races_dynamically(season_config['multiclass_races'], xml_folder_mc)
            comparison_df, _, avg_pace_cols, used_race_codes, track_names = csv_lib.process_races_into_comparison_df(mc_p2ur_race_dfs, race_codes, code_to_track, season_id, 'multiclass', 'PROTOTYPE')
            
            if comparison_df is not None:
                html_content = html_lib.generate_comparison_page(
                    comparison_df, avg_pace_cols, used_race_codes, track_names,
                    f'{championship_name} {prototype_class} Race Data', 'multiclass_p2ur_race.html', season_id,
                    f'{championship_name} {prototype_class} Race Pace Trend', 'Race Pace % (vs Alien)', mode='race',
                )
                
                with open(os.path.join(season_output_dir, 'multiclass_p2ur_race.html'), 'w', encoding='utf-8-sig') as f:
                    f.write(html_content)
                print(f"    Generated multiclass_{prototype_class.lower()}_race.html")
            else:
                print(f"    Comparison DF is None for {prototype_class} races")
        else:
            print(f"    No {prototype_class} data found for races")

        # ===== MULTICLASS PROTOTYPE QUALI PACE =====
        print(f"  [{championship_name}] {prototype_class} Quali Pace...")
        mc_p2ur_quali_dfs = {}
        
        for filename, mc_info in season_config['multiclass_qualis'].items():
            xml_path = os.path.join(xml_folder_mc, filename)
            if os.path.exists(xml_path):
                df = csv_lib.load_event_csv(xml_path, prototype_filter)
                if df is not None:
                    mc_p2ur_quali_dfs[mc_info['name']] = df
            else:
                print(f"    Not found: {xml_path}")
        
        if not mc_p2ur_quali_dfs:
            print(f"    No {prototype_class} data found for qualies")
        else:
            race_codes, track_names, code_to_track = csv_lib.load_races_dynamically(season_config['multiclass_qualis'], xml_folder_mc)
            comparison_df, _, avg_pace_cols, used_race_codes, track_names = csv_lib.process_races_into_comparison_df(mc_p2ur_quali_dfs, race_codes, code_to_track, season_id, 'multiclass', 'PROTOTYPE')
            
            if comparison_df is not None:
                html_content = html_lib.generate_comparison_page(
                    comparison_df, avg_pace_cols, used_race_codes, track_names,
                    f'{championship_name} {prototype_class} Quali Data', 'multiclass_p2ur_quali.html', season_id,
                    f'{championship_name} {prototype_class} Quali Pace Trend', 'Quali Pace % (vs Alien)', mode='quali',
                )
                
                with open(os.path.join(season_output_dir, 'multiclass_p2ur_quali.html'), 'w', encoding='utf-8-sig') as f:
                    f.write(html_content)
                print(f"    Generated multiclass_{prototype_class.lower()}_quali.html")
            else:
                print(f"    Comparison DF is None for {prototype_class} qualies")
        
        # ===== MULTICLASS GT3 RACE PACE =====
        print(f"  [{championship_name}] GT3 Race Pace...")
        mc_gt3_race_dfs = {}
        
        for filename, mc_info in season_config['multiclass_races'].items():
            xml_path = os.path.join(xml_folder_mc, filename)
            if os.path.exists(xml_path):
                df = csv_lib.load_event_csv(xml_path, 'GT3')
                if df is not None:
                    mc_gt3_race_dfs[mc_info['name']] = df
        
        if mc_gt3_race_dfs:
            race_codes, track_names, code_to_track = csv_lib.load_races_dynamically(season_config['multiclass_races'], xml_folder_mc)
            comparison_df, _, avg_pace_cols, used_race_codes, track_names = csv_lib.process_races_into_comparison_df(mc_gt3_race_dfs, race_codes, code_to_track, season_id, 'multiclass', 'GT3')
            
            if comparison_df is not None:
                html_content = html_lib.generate_comparison_page(
                    comparison_df, avg_pace_cols, used_race_codes, track_names,
                    f'{championship_name} GT3 Race Data', 'multiclass_gt3_race.html', season_id,
                    f'{championship_name} GT3 Race Pace Trend', 'Race Pace % (vs Alien)', mode='race',
                )
                
                with open(os.path.join(season_output_dir, 'multiclass_gt3_race.html'), 'w', encoding='utf-8-sig') as f:
                    f.write(html_content)
                print("    Generated multiclass_gt3_race.html")
            else:
                print("    Comparison DF is None for GT3 races")
        else:
            print("    No GT3 data found for races")
        
        # ===== MULTICLASS GT3 QUALI PACE =====
        print(f"  [{championship_name}] GT3 Quali Pace...")
        mc_gt3_quali_dfs = {}
        
        for filename, mc_info in season_config['multiclass_qualis'].items():
            xml_path = os.path.join(xml_folder_mc, filename)
            if os.path.exists(xml_path):
                df = csv_lib.load_event_csv(xml_path, 'GT3')
                if df is not None:
                    mc_gt3_quali_dfs[mc_info['name']] = df
        
        if mc_gt3_quali_dfs:
            race_codes, track_names, code_to_track = csv_lib.load_races_dynamically(season_config['multiclass_qualis'], xml_folder_mc)
            comparison_df, _, avg_pace_cols, used_race_codes, track_names = csv_lib.process_races_into_comparison_df(mc_gt3_quali_dfs, race_codes, code_to_track, season_id, 'multiclass', 'GT3')
            
            if comparison_df is not None:
                html_content = html_lib.generate_comparison_page(
                    comparison_df, avg_pace_cols, used_race_codes, track_names,
                    f'{championship_name} GT3 Quali Data', 'multiclass_gt3_quali.html', season_id,
                    f'{championship_name} GT3 Quali Pace Trend', 'Quali Pace % (vs Alien)', mode='quali',
                )
                
                with open(os.path.join(season_output_dir, 'multiclass_gt3_quali.html'), 'w', encoding='utf-8-sig') as f:
                    f.write(html_content)
                print("    Generated multiclass_gt3_quali.html")
            else:
                print("    Comparison DF is None for GT3 qualies")
        else:
            print("    No GT3 data found for qualies")
    
    # All seasons processed - print summary
    print("\n" + "=" * 60)
    print("All pages generated successfully!")


if __name__ == '__main__':
    main()
