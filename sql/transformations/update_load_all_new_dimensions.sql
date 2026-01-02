-- ============================================================================
-- Update load_all_new_dimensions() to include load_dw_dim_patient()
-- ============================================================================
-- This script updates the master transformation procedure to include patient
-- dimension loading, ensuring patient data flows from Bronze to Silver
-- automatically after ETL jobs complete.
-- ============================================================================

BEGIN;

-- Drop and recreate the procedure with load_dw_dim_patient() included
CREATE OR REPLACE PROCEDURE load_all_new_dimensions()
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Starting load_all_new_dimensions() - Master ETL';
    RAISE NOTICE '============================================================';
    
    BEGIN
        CALL load_dw_dim_site();
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'Error in load_all_new_dimensions(): Error in load_dw_dim_site(): %', SQLERRM;
    END;
    
    BEGIN
        CALL load_dw_dim_monitor();
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'Error in load_all_new_dimensions(): Error in load_dw_dim_monitor(): %', SQLERRM;
    END;
    
    BEGIN
        CALL load_dw_dim_medical_code();
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'Error in load_all_new_dimensions(): Error in load_dw_dim_medical_code(): %', SQLERRM;
    END;
    
    BEGIN
        CALL load_dw_dim_patient_engagement();
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'Error in load_all_new_dimensions(): Error in load_dw_dim_patient_engagement(): %', SQLERRM;
    END;
    
    BEGIN
        CALL load_dw_dim_patient();
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'Error in load_all_new_dimensions(): Error in load_dw_dim_patient(): %', SQLERRM;
    END;
    
    BEGIN
        CALL load_dw_dim_study();
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'Error in load_all_new_dimensions(): Error in load_dw_dim_study(): %', SQLERRM;
    END;
    
    BEGIN
        CALL load_dw_dim_subject();
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'Error in load_all_new_dimensions(): Error in load_dw_dim_subject(): %', SQLERRM;
    END;
    
    BEGIN
        CALL load_dw_dim_visit();
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'Error in load_all_new_dimensions(): Error in load_dw_dim_visit(): %', SQLERRM;
    END;
    
    BEGIN
        CALL load_dw_dim_visit_element();
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'Error in load_all_new_dimensions(): Error in load_dw_dim_visit_element(): %', SQLERRM;
    END;
    
    BEGIN
        CALL load_dw_dim_study_arm();
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'Error in load_all_new_dimensions(): Error in load_dw_dim_study_arm(): %', SQLERRM;
    END;
    
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'load_all_new_dimensions() completed successfully';
    RAISE NOTICE '============================================================';
END;
$$;

COMMENT ON PROCEDURE load_all_new_dimensions() IS 
'Master procedure to load all dimensions from Bronze (staging) to Silver layer. 
Includes: sites, monitors, medical codes, patient engagement, patients, studies, 
subjects, visits, visit elements, and study arms. Runs daily at 2 AM after ETL jobs complete.';

COMMIT;

-- Verification
SELECT 
    routine_name,
    routine_type,
    routine_definition
FROM information_schema.routines
WHERE routine_name = 'load_all_new_dimensions'
  AND routine_schema = 'public';

