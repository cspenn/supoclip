============================= test session starts ==============================
platform darwin -- Python 3.11.12, pytest-9.0.2, pluggy-1.5.0 -- /Users/cspenn/.pyenv/versions/3.11.12/bin/python3.11
cachedir: .pytest_cache
hypothesis profile 'default'
Fugue tests will be initialized with options:
PySide6 6.8.3 -- Qt runtime 6.8.3 -- Qt compiled 6.8.3
rootdir: /Users/cspenn/Documents/github/supoclip/backend
configfile: pytest.ini
testpaths: tests
plugins: mock-3.15.1, repeat-0.9.4, asyncio-1.2.0, anyio-4.9.0, xdist-3.8.0, httpx-0.35.0, hypothesis-6.148.7, fugue-0.9.1, logfire-4.14.2, Faker-37.3.0, qt-4.5.0, langsmith-0.3.45, typeguard-4.4.4, cov-7.0.0, deepeval-2.5.5
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 550 items

tests/integration/test_service_integration.py::TestVideoServiceWithPreferences::test_video_service_uses_user_preferences PASSED [  0%]
tests/integration/test_service_integration.py::TestVideoServiceWithPreferences::test_preferences_merge_with_request_options PASSED [  0%]
tests/integration/test_service_integration.py::TestFontOptionsIntegration::test_parse_then_merge_font_options PASSED [  0%]
tests/integration/test_service_integration.py::TestFontOptionsIntegration::test_partial_font_options_with_user_preferences PASSED [  0%]
tests/integration/test_service_integration.py::TestAuthDependencyIntegration::test_auth_with_user_preferences_service PASSED [  0%]
tests/integration/test_service_integration.py::TestServiceDependencyChain::test_async_service_creates_task_then_processes PASSED [  1%]
tests/integration/test_service_integration.py::TestLogoPathHandling::test_logo_path_extraction_from_preferences FAILED [  1%]
tests/integration/test_service_integration.py::TestLogoPathHandling::test_logo_passed_to_video_service PASSED [  1%]
tests/integration/test_service_integration.py::TestErrorPropagation::test_auth_error_prevents_service_call PASSED [  1%]
tests/integration/test_service_integration.py::TestErrorPropagation::test_preferences_error_propagates PASSED [  1%]
tests/integration/test_timestamp_pipeline_integration.py::TestTimestampPipelineIntegration::test_ai_segments_to_video_parser_flow PASSED [  2%]
tests/integration/test_timestamp_pipeline_integration.py::TestTimestampPipelineIntegration::test_3_clips_generation_simulation PASSED [  2%]
tests/integration/test_timestamp_pipeline_integration.py::TestTimestampPipelineIntegration::test_millisecond_precision_preserved_through_pipeline PASSED [  2%]
tests/integration/test_timestamp_pipeline_integration.py::TestTimestampPipelineIntegration::test_backward_compatibility_with_legacy_timestamps PASSED [  2%]
tests/integration/test_timestamp_pipeline_integration.py::TestTimestampPipelineIntegration::test_mixed_timestamp_formats_in_same_batch PASSED [  2%]
tests/integration/test_timestamp_pipeline_integration.py::TestTimestampPipelineIntegration::test_segment_duration_range_validation PASSED [  2%]
tests/integration/test_timestamp_pipeline_integration.py::TestEndToEndClipGeneration::test_generate_3_clips_from_groq_timestamps PASSED [  3%]
tests/repositories/test_task_repository_schema.py::test_task_creation_without_progress PASSED [  3%]
tests/repositories/test_task_repository_schema.py::test_task_status_update_with_progress_fails FAILED [  3%]
tests/repositories/test_task_repository_schema.py::test_task_status_update_with_progress_message_only_fails FAILED [  3%]
tests/repositories/test_task_repository_schema.py::test_task_get_with_progress_gracefully_handles_missing_columns FAILED [  3%]
tests/repositories/test_task_repository_schema.py::test_connection_cleanup_after_failed_update FAILED [  4%]
tests/test_api_endpoints.py::TestRootEndpoint::test_root_endpoint_returns_200 PASSED [  4%]
tests/test_api_endpoints.py::TestRootEndpoint::test_root_endpoint_response_structure FAILED [  4%]
tests/test_api_endpoints.py::TestRootEndpoint::test_root_endpoint_values FAILED [  4%]
tests/test_api_endpoints.py::TestHealthCheckEndpoints::test_basic_health_check PASSED [  4%]
tests/test_api_endpoints.py::TestHealthCheckEndpoints::test_database_health_check PASSED [  4%]
tests/test_api_endpoints.py::TestHealthCheckEndpoints::test_redis_health_check_endpoint_exists FAILED [  5%]
tests/test_api_endpoints.py::TestAPIDocumentation::test_swagger_docs_available PASSED [  5%]
tests/test_api_endpoints.py::TestAPIDocumentation::test_openapi_schema_available PASSED [  5%]
tests/test_api_endpoints.py::TestAPIStructure::test_api_version_in_schema PASSED [  5%]
tests/test_api_endpoints.py::TestAPIStructure::test_api_title_in_schema PASSED [  5%]
tests/test_api_endpoints.py::TestAPIStructure::test_api_description_in_schema PASSED [  6%]
tests/test_api_endpoints.py::TestCORSConfiguration::test_cors_headers_present PASSED [  6%]
tests/test_api_endpoints.py::TestErrorHandling::test_nonexistent_endpoint_404 PASSED [  6%]
tests/test_api_endpoints.py::TestErrorHandling::test_method_not_allowed PASSED [  6%]
tests/test_api_endpoints.py::TestBasicAPIIntegration::test_health_check_chain PASSED [  6%]
tests/test_api_endpoints.py::TestBasicAPIIntegration::test_api_responsiveness PASSED [  6%]
tests/test_api_endpoints.py::TestBasicAPIIntegration::test_api_json_responses PASSED [  7%]
tests/test_api_endpoints.py::TestStaticFileServing::test_clips_directory_mount PASSED [  7%]
tests/test_api_endpoints.py::TestAPIContentTypes::test_json_content_type_default PASSED [  7%]
tests/test_api_endpoints.py::TestAPIContentTypes::test_health_json_content_type PASSED [  7%]
tests/test_api_endpoints.py::TestDatabaseDependencyInjection::test_database_health_uses_session PASSED [  7%]
tests/test_caption_clipping.py::test_dynamic_margin_calculation PASSED   [  8%]
tests/test_caption_clipping_1080p.py::test_resolution_clipping PASSED    [  8%]
tests/test_caption_clipping_1080p.py::test_1080p_with_fixes PASSED       [  8%]
tests/test_caption_compositing.py::test_composite_clipping PASSED        [  8%]
tests/test_caption_compositing.py::test_safe_positioning PASSED          [  8%]
tests/test_caption_fix_verification.py::test_fix_verification PASSED     [  8%]
tests/test_caption_reconstruction.py::TestWordReconstruction::test_reconstruct_simple_broken_words PASSED [  9%]
tests/test_caption_reconstruction.py::TestWordReconstruction::test_missing_groq_key_returns_original PASSED [  9%]
tests/test_caption_reconstruction.py::TestWordReconstruction::test_align_reconstructed_words_basic PASSED [  9%]
tests/test_caption_reconstruction.py::TestWordReconstruction::test_align_with_empty_reconstructed_text PASSED [  9%]
tests/test_caption_reconstruction.py::TestWordReconstruction::test_align_preserves_confidence PASSED [  9%]
tests/test_caption_reconstruction.py::TestCaptionQuality::test_word_boundaries_preserved PASSED [ 10%]
tests/test_clean_start_rules.py::TestCleanStartRulesValidation::test_segment_starting_with_and_rejected PASSED [ 10%]
tests/test_clean_start_rules.py::TestCleanStartRulesValidation::test_segment_starting_with_but_rejected PASSED [ 10%]
tests/test_clean_start_rules.py::TestCleanStartRulesValidation::test_segment_starting_with_so_rejected PASSED [ 10%]
tests/test_clean_start_rules.py::TestCleanStartRulesValidation::test_segment_starting_with_well_rejected PASSED [ 10%]
tests/test_clean_start_rules.py::TestCleanStartRulesValidation::test_segment_starting_with_because_rejected PASSED [ 10%]
tests/test_clean_start_rules.py::TestCleanStartRulesValidation::test_segment_starting_with_also_rejected PASSED [ 11%]
tests/test_clean_start_rules.py::TestCleanStartRulesValidation::test_segment_starting_with_um_rejected PASSED [ 11%]
tests/test_clean_start_rules.py::TestCleanStartRulesValidation::test_segment_starting_with_uh_rejected PASSED [ 11%]
tests/test_clean_start_rules.py::TestCleanStartRulesValidation::test_segment_starting_with_you_know_rejected PASSED [ 11%]
tests/test_clean_start_rules.py::TestCleanStartRulesValidation::test_segment_starting_with_i_mean_rejected PASSED [ 11%]
tests/test_clean_start_rules.py::TestCleanStartRulesValidation::test_segment_starting_with_like_rejected PASSED [ 12%]
tests/test_clean_start_rules.py::TestCleanStartRulesCaseSensitivity::test_uppercase_and_rejected PASSED [ 12%]
tests/test_clean_start_rules.py::TestCleanStartRulesCaseSensitivity::test_mixed_case_but_rejected PASSED [ 12%]
tests/test_clean_start_rules.py::TestCleanStartRulesCaseSensitivity::test_uppercase_so_rejected PASSED [ 12%]
tests/test_clean_start_rules.py::TestCleanStartRulesCaseSensitivity::test_mixed_case_because_rejected PASSED [ 12%]
tests/test_clean_start_rules.py::TestCleanStartRulesAcceptance::test_segments_with_clean_starts_accepted PASSED [ 12%]
tests/test_clean_start_rules.py::TestCleanStartRulesAcceptance::test_sentence_starting_with_and_in_middle_accepted PASSED [ 13%]
tests/test_clean_start_rules.py::TestCleanStartRulesAcceptance::test_word_containing_forbidden_word_accepted PASSED [ 13%]
tests/test_clean_start_rules.py::TestCleanStartRulesAcceptance::test_android_word_starting_accepted PASSED [ 13%]
tests/test_clean_start_rules.py::TestCleanStartRulesIntegration::test_validation_logs_warnings_for_skipped_segments PASSED [ 13%]
tests/test_clean_start_rules.py::TestCleanStartRulesIntegration::test_segments_without_forbidden_words_pass_validation PASSED [ 13%]
tests/test_clean_start_rules.py::TestCleanStartRulesIntegration::test_multiple_forbidden_words_in_sequence_rejected PASSED [ 14%]
tests/test_clip_parameter_fix.py::test_parameter_shadowing_fix PASSED    [ 14%]
tests/test_clip_save_verification.py::test_clip_save PASSED              [ 14%]
tests/test_configuration.py::TestConfigLoading::test_config_initialization PASSED [ 14%]
tests/test_configuration.py::TestConfigLoading::test_mlx_whisper_model_default FAILED [ 14%]
tests/test_configuration.py::TestConfigLoading::test_mlx_whisper_model_from_env FAILED [ 14%]
tests/test_configuration.py::TestConfigLoading::test_llm_model_default PASSED [ 15%]
tests/test_configuration.py::TestConfigLoading::test_llm_model_from_env PASSED [ 15%]
tests/test_configuration.py::TestConfigLoading::test_api_keys_optional PASSED [ 15%]
tests/test_configuration.py::TestVideoProcessingConfig::test_max_video_duration_default PASSED [ 15%]
tests/test_configuration.py::TestVideoProcessingConfig::test_max_video_duration_from_env PASSED [ 15%]
tests/test_configuration.py::TestVideoProcessingConfig::test_output_dir_default PASSED [ 16%]
tests/test_configuration.py::TestVideoProcessingConfig::test_output_dir_from_env PASSED [ 16%]
tests/test_configuration.py::TestVideoProcessingConfig::test_max_clips_default PASSED [ 16%]
tests/test_configuration.py::TestVideoProcessingConfig::test_max_clips_from_env PASSED [ 16%]
tests/test_configuration.py::TestVideoProcessingConfig::test_clip_duration_default PASSED [ 16%]
tests/test_configuration.py::TestVideoProcessingConfig::test_clip_duration_from_env PASSED [ 16%]
tests/test_configuration.py::TestDatabaseConfig::test_database_url_default PASSED [ 17%]
tests/test_configuration.py::TestDatabaseConfig::test_database_url_from_env PASSED [ 17%]
tests/test_configuration.py::TestDatabaseConfig::test_temp_dir_default PASSED [ 17%]
tests/test_configuration.py::TestDatabaseConfig::test_temp_dir_from_env PASSED [ 17%]
tests/test_configuration.py::TestJobQueueConfig::test_max_workers_default PASSED [ 17%]
tests/test_configuration.py::TestJobQueueConfig::test_max_workers_from_env PASSED [ 18%]
tests/test_configuration.py::TestJobQueueConfig::test_worker_timeout_default PASSED [ 18%]
tests/test_configuration.py::TestJobQueueConfig::test_worker_timeout_from_env PASSED [ 18%]
tests/test_configuration.py::TestConfigTypeConversion::test_integer_type_conversion PASSED [ 18%]
tests/test_configuration.py::TestConfigTypeConversion::test_string_type_preserved PASSED [ 18%]
tests/test_configuration.py::TestConfigValidation::test_empty_string_handling PASSED [ 18%]
tests/test_configuration.py::TestConfigValidation::test_whitespace_handling PASSED [ 19%]
tests/test_configuration.py::TestConfigValidation::test_special_characters_in_paths PASSED [ 19%]
tests/test_configuration.py::TestConfigValidation::test_multiple_config_instances_independent PASSED [ 19%]
tests/test_configuration.py::TestOfflineCapability::test_no_external_api_required_by_default PASSED [ 19%]
tests/test_configuration.py::TestOfflineCapability::test_mlx_whisper_available_offline FAILED [ 19%]
tests/test_configuration.py::TestOfflineCapability::test_local_job_queue_configuration PASSED [ 20%]
tests/test_database.py::TestDatabaseInitialization::test_database_tables_created PASSED [ 20%]
tests/test_database.py::TestDatabaseInitialization::test_base_metadata_contains_all_models PASSED [ 20%]
tests/test_database.py::TestDatabaseInitialization::test_user_table_has_required_fields PASSED [ 20%]
tests/test_database.py::TestDatabaseInitialization::test_task_table_has_required_fields PASSED [ 20%]
tests/test_database.py::TestUserCRUD::test_create_user PASSED            [ 20%]
tests/test_database.py::TestUserCRUD::test_create_user_with_defaults PASSED [ 21%]
tests/test_database.py::TestUserCRUD::test_update_user PASSED            [ 21%]
tests/test_database.py::TestUserCRUD::test_user_email_unique PASSED      [ 21%]
tests/test_database.py::TestUserCRUD::test_user_relationships PASSED     [ 21%]
tests/test_database.py::TestTaskOperations::test_create_task PASSED      [ 21%]
tests/test_database.py::TestTaskOperations::test_task_status_update PASSED [ 22%]
tests/test_database.py::TestTaskOperations::test_task_default_font_settings PASSED [ 22%]
tests/test_database.py::TestTaskOperations::test_task_user_relationship PASSED [ 22%]
tests/test_database.py::TestTaskOperations::test_task_cascade_delete PASSED [ 22%]
tests/test_database.py::TestSourceOperations::test_create_source PASSED  [ 22%]
tests/test_database.py::TestSourceOperations::test_source_type_constraint PASSED [ 22%]
tests/test_database.py::TestSourceOperations::test_source_task_relationship PASSED [ 23%]
tests/test_database.py::TestGeneratedClipOperations::test_create_generated_clip PASSED [ 23%]
tests/test_database.py::TestGeneratedClipOperations::test_clip_task_relationship PASSED [ 23%]
tests/test_database.py::TestGeneratedClipOperations::test_clip_cascade_delete PASSED [ 23%]
tests/test_database.py::TestTimestampHandling::test_created_at_auto_set PASSED [ 23%]
tests/test_database.py::TestTimestampHandling::test_updated_at_auto_set PASSED [ 24%]
tests/test_default_prompt_endpoint.py::TestDefaultPromptEndpoint::test_get_default_prompt_returns_200 PASSED [ 24%]
tests/test_default_prompt_endpoint.py::TestDefaultPromptEndpoint::test_get_default_prompt_returns_current_system_prompt PASSED [ 24%]
tests/test_default_prompt_endpoint.py::TestDefaultPromptEndpoint::test_default_prompt_includes_clean_start_rules PASSED [ 24%]
tests/test_default_prompt_endpoint.py::TestDefaultPromptEndpoint::test_default_prompt_includes_dynamic_placeholders PASSED [ 24%]
tests/test_default_prompt_endpoint.py::TestDefaultPromptEndpoint::test_default_prompt_valid_for_ai_analysis PASSED [ 24%]
tests/test_default_prompt_endpoint.py::TestDefaultPromptEndpoint::test_default_prompt_response_structure PASSED [ 25%]
tests/test_default_prompt_endpoint.py::TestDefaultPromptEndpoint::test_default_prompt_contains_segment_selection_guidance PASSED [ 25%]
tests/test_default_prompt_endpoint.py::TestDefaultPromptEndpoint::test_default_prompt_consistency PASSED [ 25%]
tests/test_descender_clipping.py::test_descender_clipping_with_stroke PASSED [ 25%]
tests/test_descender_clipping.py::test_actual_user_scenario PASSED       [ 25%]
tests/test_e2e_pipeline.py::test_complete_pipeline PASSED                [ 26%]
tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_database_initialization PASSED [ 26%]
tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_create_task_in_database PASSED [ 26%]
tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_store_generated_clip_metadata PASSED [ 26%]
tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_api_health_check PASSED [ 26%]
tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_api_root_endpoint FAILED [ 26%]
tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_api_documentation_available PASSED [ 27%]
tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_local_llm_configuration PASSED [ 27%]
tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_mlx_whisper_configuration FAILED [ 27%]
tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_sqlite_database_configuration PASSED [ 27%]
tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_test_video_created PASSED [ 27%]
tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_transcription_with_mlx_whisper SKIPPED [ 28%]
tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_ai_segment_analysis_structure PASSED [ 28%]
tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_clip_generation_no_external_apis PASSED [ 28%]
tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_performance_baseline_configuration FAILED [ 28%]
tests/test_end_to_end.py::TestE2EAPIEndpoints::test_get_fonts_endpoint PASSED [ 28%]
tests/test_end_to_end.py::TestE2EAPIEndpoints::test_get_transitions_endpoint PASSED [ 28%]
tests/test_end_to_end.py::TestE2EAPIEndpoints::test_task_creation_endpoint_requires_auth FAILED [ 29%]
tests/test_end_to_end.py::TestE2EAPIEndpoints::test_database_health_check PASSED [ 29%]
tests/test_end_to_end.py::TestE2EVideoFilesAndMetadata::test_clip_output_directory_structure PASSED [ 29%]
tests/test_end_to_end.py::TestE2EVideoFilesAndMetadata::test_store_clip_metadata_with_timestamps PASSED [ 29%]
tests/test_end_to_end.py::TestE2EVideoFilesAndMetadata::test_mp4_file_format_validity PASSED [ 29%]
tests/test_end_to_end.py::TestE2EPerformanceMetrics::test_transcription_time_measurement PASSED [ 30%]
tests/test_end_to_end.py::TestE2EPerformanceMetrics::test_clip_generation_time_measurement PASSED [ 30%]
tests/test_end_to_end.py::TestE2EPerformanceMetrics::test_end_to_end_workflow_timing PASSED [ 30%]
tests/test_end_to_end.py::TestE2ELocalFirstOperation::test_no_cloud_api_keys_required PASSED [ 30%]
tests/test_end_to_end.py::TestE2ELocalFirstOperation::test_database_local_only PASSED [ 30%]
tests/test_end_to_end.py::TestE2ELocalFirstOperation::test_transcription_local_mlx FAILED [ 30%]
tests/test_end_to_end.py::TestE2ELocalFirstOperation::test_job_queue_local_asyncio PASSED [ 31%]
tests/test_end_to_end.py::TestE2EDatabaseOperations::test_insert_and_retrieve_task PASSED [ 31%]
tests/test_end_to_end.py::TestE2EDatabaseOperations::test_multiple_clips_per_task PASSED [ 31%]
tests/test_end_to_end.py::TestE2EDatabaseOperations::test_update_task_status PASSED [ 31%]
tests/test_font_cutoff_and_short_clips.py::TestFontCutoffIssue::test_caption_method_causes_text_cutoff PASSED [ 31%]
tests/test_font_cutoff_and_short_clips.py::TestFontCutoffIssue::test_barlow_condensed_bold_cutoff_reproduction SKIPPED [ 32%]
tests/test_font_cutoff_and_short_clips.py::TestShortClipsIssue::test_system_prompt_has_hardcoded_durations PASSED [ 32%]
tests/test_font_cutoff_and_short_clips.py::TestShortClipsIssue::test_ai_generates_short_clips_despite_long_settings PASSED [ 32%]
tests/test_font_cutoff_and_short_clips.py::TestShortClipsIssue::test_validation_hardcoded_minimum PASSED [ 32%]
tests/test_font_cutoff_and_short_clips.py::TestActualUserScenario::test_user_scenario_reproduction SKIPPED [ 32%]
tests/test_font_service.py::test_font_metadata_creation PASSED           [ 32%]
tests/test_font_service.py::test_system_font_database_model PASSED       [ 33%]
tests/test_font_service.py::test_system_font_unique_constraint PASSED    [ 33%]
tests/test_font_service.py::test_system_font_source_check_constraint PASSED [ 33%]
tests/test_font_service.py::test_system_font_filtering_by_source PASSED  [ 33%]
tests/test_font_service.py::test_system_font_search_by_family PASSED     [ 33%]
tests/test_fonts_api_endpoints.py::TestFontsListEndpoint::test_list_all_fonts PASSED [ 34%]
tests/test_fonts_api_endpoints.py::TestFontsListEndpoint::test_list_fonts_with_bundled_filter PASSED [ 34%]
tests/test_fonts_api_endpoints.py::TestFontsListEndpoint::test_list_fonts_with_system_filter PASSED [ 34%]
tests/test_fonts_api_endpoints.py::TestFontsListEndpoint::test_list_fonts_response_format PASSED [ 34%]
tests/test_fonts_api_endpoints.py::TestFontSearchEndpoint::test_search_fonts_by_name PASSED [ 34%]
tests/test_fonts_api_endpoints.py::TestFontSearchEndpoint::test_search_fonts_by_family PASSED [ 34%]
tests/test_fonts_api_endpoints.py::TestFontSearchEndpoint::test_search_nonexistent_font PASSED [ 35%]
tests/test_fonts_api_endpoints.py::TestFontSearchEndpoint::test_search_missing_query_parameter PASSED [ 35%]
tests/test_fonts_api_endpoints.py::TestFontSearchEndpoint::test_search_query_too_short PASSED [ 35%]
tests/test_fonts_api_endpoints.py::TestFontSearchEndpoint::test_search_case_insensitive PASSED [ 35%]
tests/test_fonts_api_endpoints.py::TestFontRefreshEndpoint::test_refresh_fonts PASSED [ 35%]
tests/test_fonts_api_endpoints.py::TestFontRefreshEndpoint::test_refresh_fonts_returns_proper_structure PASSED [ 36%]
tests/test_fonts_api_endpoints.py::TestFontFileServingEndpoint::test_serve_nonexistent_font_file PASSED [ 36%]
tests/test_fonts_api_endpoints.py::TestFontFileServingEndpoint::test_serve_existing_font_file PASSED [ 36%]
tests/test_fonts_api_endpoints.py::TestFontsEndpointErrorHandling::test_invalid_source_filter PASSED [ 36%]
tests/test_fonts_api_endpoints.py::TestFontsEndpointErrorHandling::test_special_characters_in_search PASSED [ 36%]
tests/test_fonts_api_endpoints.py::TestFontsEndpointErrorHandling::test_very_long_search_query PASSED [ 36%]
tests/test_fonts_api_endpoints.py::TestEdgeCasesAndConcurrency::test_empty_font_list PASSED [ 37%]
tests/test_groq_fallback.py::test_groq_failure_falls_back_to_pydantic_ai FAILED [ 37%]
tests/test_groq_fallback.py::test_groq_success_uses_structured_outputs PASSED [ 37%]
tests/test_groq_integration.py::test_groq_config PASSED                  [ 37%]
tests/test_local_llm_config.py::TestLocalLLMConfiguration::test_local_llm_enabled_default PASSED [ 37%]
tests/test_local_llm_config.py::TestLocalLLMConfiguration::test_local_llm_enabled_from_env PASSED [ 38%]
tests/test_local_llm_config.py::TestLocalLLMConfiguration::test_local_llm_base_url_default PASSED [ 38%]
tests/test_local_llm_config.py::TestLocalLLMConfiguration::test_local_llm_base_url_from_env PASSED [ 38%]
tests/test_local_llm_config.py::TestLocalLLMConfiguration::test_local_llm_model_default PASSED [ 38%]
tests/test_local_llm_config.py::TestLocalLLMConfiguration::test_local_llm_model_from_env PASSED [ 38%]
tests/test_local_llm_config.py::TestLocalLLMConfiguration::test_local_llm_api_key_default PASSED [ 38%]
tests/test_local_llm_config.py::TestLocalLLMConfiguration::test_local_llm_api_key_from_env PASSED [ 39%]
tests/test_local_llm_config.py::TestCloudLLMConfiguration::test_cloud_llm_model_default_empty PASSED [ 39%]
tests/test_local_llm_config.py::TestCloudLLMConfiguration::test_cloud_llm_model_from_env PASSED [ 39%]
tests/test_local_llm_config.py::TestCloudLLMConfiguration::test_cloud_api_keys_default_empty PASSED [ 39%]
tests/test_local_llm_config.py::TestCloudLLMConfiguration::test_openai_api_key_from_env PASSED [ 39%]
tests/test_local_llm_config.py::TestCloudLLMConfiguration::test_google_api_key_from_env PASSED [ 40%]
tests/test_local_llm_config.py::TestCloudLLMConfiguration::test_anthropic_api_key_from_env PASSED [ 40%]
tests/test_local_llm_config.py::TestLLMModelSelection::test_get_llm_model_returns_openai_chat_model_when_local_enabled PASSED [ 40%]
tests/test_local_llm_config.py::TestLLMModelSelection::test_get_llm_model_returns_string_when_cloud PASSED [ 40%]
tests/test_local_llm_config.py::TestLLMModelSelection::test_get_llm_model_raises_when_no_llm_configured PASSED [ 40%]
tests/test_local_llm_config.py::TestLLMModelSelection::test_local_llm_takes_priority_over_cloud PASSED [ 40%]
tests/test_local_llm_config.py::TestCloudAPIKeyDetection::test_has_cloud_api_key_returns_false_when_all_empty FAILED [ 41%]
tests/test_local_llm_config.py::TestCloudAPIKeyDetection::test_has_cloud_api_key_returns_true_with_openai PASSED [ 41%]
tests/test_local_llm_config.py::TestCloudAPIKeyDetection::test_has_cloud_api_key_returns_true_with_google PASSED [ 41%]
tests/test_local_llm_config.py::TestCloudAPIKeyDetection::test_has_cloud_api_key_returns_true_with_anthropic PASSED [ 41%]
tests/test_local_llm_config.py::TestLocalLLMModelCreation::test_create_local_llm_model_returns_openai_chat_model PASSED [ 41%]
tests/test_local_llm_config.py::TestLocalLLMModelCreation::test_create_local_llm_model_uses_custom_base_url PASSED [ 42%]
tests/test_local_llm_config.py::TestLocalLLMModelCreation::test_create_local_llm_model_uses_custom_model_name PASSED [ 42%]
tests/test_local_llm_config.py::TestConfigurationErrorMessages::test_error_message_suggests_local_and_cloud_options PASSED [ 42%]
tests/test_local_llm_config.py::TestConfigurationBackwardCompatibility::test_cloud_only_config_still_works PASSED [ 42%]
tests/test_local_llm_config.py::TestConfigurationBackwardCompatibility::test_local_first_is_transparent_to_cloud_users PASSED [ 42%]
tests/test_local_queue.py::TestLocalJobQueueInitialization::test_queue_initialization PASSED [ 42%]
tests/test_local_queue.py::TestLocalJobQueueInitialization::test_custom_worker_count PASSED [ 43%]
tests/test_local_queue.py::TestLocalJobQueueInitialization::test_queue_internal_state PASSED [ 43%]
tests/test_local_queue.py::TestJobDataStructure::test_job_creation PASSED [ 43%]
tests/test_local_queue.py::TestJobDataStructure::test_job_with_arguments PASSED [ 43%]
tests/test_local_queue.py::TestJobEnqueueing::test_enqueue_job PASSED    [ 43%]
tests/test_local_queue.py::TestJobEnqueueing::test_enqueue_multiple_jobs PASSED [ 44%]
tests/test_local_queue.py::TestJobEnqueueing::test_enqueue_job_with_args_kwargs PASSED [ 44%]
tests/test_local_queue.py::TestJobProcessing::test_worker_processes_job PASSED [ 44%]
tests/test_local_queue.py::TestJobProcessing::test_worker_processes_job_with_args PASSED [ 44%]
tests/test_local_queue.py::TestJobProcessing::test_multiple_workers_process_jobs PASSED [ 44%]
tests/test_local_queue.py::TestJobStatusTracking::test_job_status_queued PASSED [ 44%]
tests/test_local_queue.py::TestJobStatusTracking::test_get_job_status PASSED [ 45%]
tests/test_local_queue.py::TestJobStatusTracking::test_get_job_result_pending PASSED [ 45%]
tests/test_local_queue.py::TestJobStatusTracking::test_get_nonexistent_job PASSED [ 45%]
tests/test_local_queue.py::TestJobStatusTracking::test_job_timestamps PASSED [ 45%]
tests/test_local_queue.py::TestErrorHandling::test_job_error_handling PASSED [ 45%]
tests/test_local_queue.py::TestErrorHandling::test_job_error_with_result_none PASSED [ 46%]
tests/test_local_queue.py::TestWorkerLifecycle::test_start_workers PASSED [ 46%]
tests/test_local_queue.py::TestWorkerLifecycle::test_stop_workers PASSED [ 46%]
tests/test_local_queue.py::TestWorkerLifecycle::test_start_workers_idempotent PASSED [ 46%]
tests/test_local_queue.py::TestWorkerLifecycle::test_queue_with_context_manager_pattern PASSED [ 46%]
tests/test_local_queue.py::TestJobQueueIntegration::test_full_job_lifecycle PASSED [ 46%]
tests/test_local_queue.py::TestJobQueueIntegration::test_sequential_jobs PASSED [ 47%]
tests/test_logo_pipeline.py::TestLogoParameterPassing::test_logo_params_in_worker_task PASSED [ 47%]
tests/test_logo_pipeline.py::TestLogoParameterPassing::test_logo_params_in_task_service PASSED [ 47%]
tests/test_logo_pipeline.py::TestLogoParameterPassing::test_logo_params_in_video_service PASSED [ 47%]
tests/test_logo_pipeline.py::TestLogoParameterPassing::test_logo_params_passed_to_clip_creation FAILED [ 47%]
tests/test_logo_pipeline.py::TestLogoParameterPassing::test_logo_overlay_code_executes FAILED [ 48%]
tests/test_logo_pipeline.py::test_logo_file_exists SKIPPED (Test log...) [ 48%]
tests/test_logo_pipeline.py::test_logo_overlay_code_exists FAILED        [ 48%]
tests/test_logo_upload.py::test_logo_upload PASSED                       [ 48%]
tests/test_logo_upload_feature.py::TestLogoUploadEndpoint::test_logo_upload_accepts_png_file FAILED [ 48%]
tests/test_logo_upload_feature.py::TestLogoUploadEndpoint::test_logo_upload_accepts_jpg_file FAILED [ 48%]
tests/test_logo_upload_feature.py::TestLogoUploadEndpoint::test_logo_upload_rejects_non_image_files FAILED [ 49%]
tests/test_logo_upload_feature.py::TestLogoUploadEndpoint::test_logo_upload_missing_file_returns_400 FAILED [ 49%]
tests/test_logo_upload_feature.py::TestLogoUploadEndpoint::test_logo_upload_missing_user_id_returns_401 PASSED [ 49%]
tests/test_logo_upload_feature.py::TestLogoFileHandling::test_logo_resize_to_60px PASSED [ 49%]
tests/test_logo_upload_feature.py::TestLogoFileHandling::test_logo_saved_to_correct_directory PASSED [ 49%]
tests/test_logo_upload_feature.py::TestLogoFileHandling::test_user_database_updated_with_logo_path FAILED [ 50%]
tests/test_logo_upload_feature.py::TestLogoCornerPositionValidation::test_corner_position_top_left_valid PASSED [ 50%]
tests/test_logo_upload_feature.py::TestLogoCornerPositionValidation::test_corner_position_top_right_valid PASSED [ 50%]
tests/test_logo_upload_feature.py::TestLogoCornerPositionValidation::test_corner_position_bottom_left_valid PASSED [ 50%]
tests/test_logo_upload_feature.py::TestLogoCornerPositionValidation::test_corner_position_bottom_right_valid PASSED [ 50%]
tests/test_logo_upload_feature.py::TestLogoCornerPositionValidation::test_invalid_corner_position_rejected PASSED [ 50%]
tests/test_logo_upload_feature.py::TestLogoCornerPositionValidation::test_corner_position_case_sensitive PASSED [ 51%]
tests/test_logo_upload_feature.py::TestLogoOverlayOnClips::test_logo_overlay_applied_to_generated_clips PASSED [ 51%]
tests/test_logo_upload_feature.py::TestLogoOverlayOnClips::test_logo_appears_at_correct_corner_position_top_right PASSED [ 51%]
tests/test_logo_upload_feature.py::TestLogoOverlayOnClips::test_logo_appears_at_correct_corner_position_bottom_left PASSED [ 51%]
tests/test_logo_upload_feature.py::TestLogoOverlayOnClips::test_logo_transparency_preserved_in_rgba_conversion PASSED [ 51%]
tests/test_logo_upload_feature.py::TestLogoConcurrency::test_concurrent_logo_uploads_dont_conflict PASSED [ 52%]
tests/test_offline_capability.py::TestOfflineDatabase::test_sqlite_default_database PASSED [ 52%]
tests/test_offline_capability.py::TestOfflineDatabase::test_no_postgresql_required PASSED [ 52%]
tests/test_offline_capability.py::TestOfflineDatabase::test_database_creates_local_file PASSED [ 52%]
tests/test_offline_capability.py::TestOfflineTranscription::test_parakeet_default PASSED [ 52%]
tests/test_offline_capability.py::TestOfflineTranscription::test_parakeet_not_cloud_service PASSED [ 52%]
tests/test_offline_capability.py::TestOfflineTranscription::test_no_assembly_ai_required PASSED [ 53%]
tests/test_offline_capability.py::TestOfflineJobQueue::test_local_queue_available PASSED [ 53%]
tests/test_offline_capability.py::TestOfflineJobQueue::test_no_redis_required PASSED [ 53%]
tests/test_offline_capability.py::TestOfflineJobQueue::test_local_queue_no_redis_dependency PASSED [ 53%]
tests/test_offline_capability.py::TestOfflineAPIOperation::test_health_check_works_offline PASSED [ 53%]
tests/test_offline_capability.py::TestOfflineAPIOperation::test_database_health_without_redis PASSED [ 54%]
tests/test_offline_capability.py::TestOfflineAPIOperation::test_root_endpoint_offline PASSED [ 54%]
tests/test_offline_capability.py::TestOfflineConfiguration::test_config_without_api_keys PASSED [ 54%]
tests/test_offline_capability.py::TestOfflineConfiguration::test_default_llm_configured PASSED [ 54%]
tests/test_offline_capability.py::TestOfflineConfiguration::test_all_required_settings_offline PASSED [ 54%]
tests/test_offline_capability.py::TestNoExternalAPICallsByDefault::test_no_openai_call_without_key PASSED [ 54%]
tests/test_offline_capability.py::TestNoExternalAPICallsByDefault::test_no_google_api_call_without_key PASSED [ 55%]
tests/test_offline_capability.py::TestNoExternalAPICallsByDefault::test_no_anthropic_call_without_key PASSED [ 55%]
tests/test_offline_capability.py::TestOfflineDirectory::test_temp_directory_local PASSED [ 55%]
tests/test_offline_capability.py::TestOfflineDirectory::test_output_directory_local PASSED [ 55%]
tests/test_offline_capability.py::TestOfflineDirectory::test_clips_stored_locally PASSED [ 55%]
tests/test_offline_capability.py::TestLocalAssetsAvailability::test_fonts_directory_exists PASSED [ 56%]
tests/test_offline_capability.py::TestLocalAssetsAvailability::test_transitions_directory_exists PASSED [ 56%]
tests/test_offline_capability.py::TestOfflineScenarios::test_application_starts_offline PASSED [ 56%]
tests/test_offline_capability.py::TestOfflineScenarios::test_database_operations_offline PASSED [ 56%]
tests/test_offline_capability.py::TestOfflineScenarios::test_job_queue_offline PASSED [ 56%]
tests/test_offline_capability.py::TestOfflineScenarios::test_file_storage_offline PASSED [ 56%]
tests/test_offline_capability.py::TestLocalLLMOfflineOperation::test_local_llm_configured_by_default PASSED [ 57%]
tests/test_offline_capability.py::TestLocalLLMOfflineOperation::test_local_llm_no_api_key_required PASSED [ 57%]
tests/test_offline_capability.py::TestLocalLLMOfflineOperation::test_local_llm_base_url_configurable PASSED [ 57%]
tests/test_offline_capability.py::TestLocalLLMOfflineOperation::test_local_llm_default_endpoint PASSED [ 57%]
tests/test_offline_capability.py::TestLocalLLMOfflineOperation::test_cloud_fallback_when_local_disabled PASSED [ 57%]
tests/test_offline_capability.py::TestLocalLLMOfflineOperation::test_full_offline_pipeline_configured PASSED [ 58%]
tests/test_offline_capability.py::TestLocalLLMOfflineOperation::test_no_api_calls_with_local_llm_enabled PASSED [ 58%]
tests/test_offline_capability.py::TestLocalLLMOfflineOperation::test_local_llm_model_name_configurable PASSED [ 58%]
tests/test_offline_capability.py::TestLocalLLMOfflineOperation::test_local_llm_cost_zero_when_enabled PASSED [ 58%]
tests/test_offline_capability.py::TestLocalLLMOfflineOperation::test_error_message_helpful_when_misconfigured PASSED [ 58%]
tests/test_parameter_flow_fixes.py::TestClipLengthParametersPassedThroughPipeline::test_analyze_transcript_receives_clip_length_params PASSED [ 58%]
tests/test_parameter_flow_fixes.py::TestClipLengthParametersPassedThroughPipeline::test_process_video_complete_passes_clip_length_to_analyze PASSED [ 59%]
tests/test_parameter_flow_fixes.py::TestVideoServiceLogsParameters::test_font_parameters_logged PASSED [ 59%]
tests/test_parameter_flow_fixes.py::TestIntegrationParameterFlow::test_full_parameter_flow_from_api_to_video_creation PASSED [ 59%]
tests/test_parameter_flow_fixes_simple.py::TestClipLengthParametersFlowThroughPipeline::test_analyze_transcript_receives_clip_length_params PASSED [ 59%]
tests/test_parameter_flow_fixes_simple.py::TestClipLengthParametersFlowThroughPipeline::test_process_video_complete_passes_clip_length_to_analyze PASSED [ 59%]
tests/test_parameter_flow_fixes_simple.py::TestVideoServiceLogsParameters::test_font_parameters_logged PASSED [ 60%]
tests/test_parameter_flow_fixes_simple.py::TestVideoServiceLogsParameters::test_clip_length_parameters_logged PASSED [ 60%]
tests/test_parameter_flow_fixes_simple.py::TestResolveFontPathFunctionality::test_resolve_font_path_exists_and_returns_string PASSED [ 60%]
tests/test_parameter_flow_fixes_simple.py::TestResolveFontPathFunctionality::test_resolve_font_path_fallback_includes_default_font PASSED [ 60%]
tests/test_parameter_flow_fixes_simple.py::TestResolveFontPathFunctionality::test_resolve_font_path_with_database_lookup PASSED [ 60%]
tests/test_parameter_flow_fixes_simple.py::TestFunctionSignatures::test_video_service_process_complete_has_clip_length_params PASSED [ 60%]
tests/test_parameter_flow_fixes_simple.py::TestFunctionSignatures::test_video_service_analyze_transcript_has_clip_length_params PASSED [ 61%]
tests/test_parameter_flow_fixes_simple.py::test_all_three_fixes_documented PASSED [ 61%]
tests/test_parameter_flow_issues.py::TestFontFallbackWhenSystemFontNotAccessible::test_font_fallback_when_bundled_not_found PASSED [ 61%]
tests/test_parameter_flow_issues.py::TestFontFallbackWhenSystemFontNotAccessible::test_font_selection_without_variations_check PASSED [ 61%]
tests/test_parameter_flow_issues.py::TestClipLengthUsesDefaultsNotUserValues::test_clip_length_defaults_hardcoded PASSED [ 61%]
tests/test_parameter_flow_issues.py::TestClipLengthUsesDefaultsNotUserValues::test_process_video_complete_accepts_clip_length_params PASSED [ 62%]
tests/test_parameter_flow_issues.py::TestMissingParameterLogging::test_video_service_logs_parameters PASSED [ 62%]
tests/test_parameter_flow_issues.py::TestSystemFontDatabaseLookup::test_resolve_font_path_queries_system_fonts_table PASSED [ 62%]
tests/test_parameter_flow_issues.py::TestFontNameVariations::test_font_variations_are_attempted PASSED [ 62%]
tests/test_parameter_flow_issues.py::test_suite_metadata PASSED          [ 62%]
tests/test_srt_format_transcript.py::TestSRTFormatBasics::test_format_transcript_returns_proper_srt_format PASSED [ 62%]
tests/test_srt_format_transcript.py::TestSRTFormatBasics::test_format_transcript_timestamp_format_mm_ss_mmm PASSED [ 63%]
tests/test_srt_format_transcript.py::TestSRTFormatBasics::test_format_transcript_millisecond_precision_preserved PASSED [ 63%]
tests/test_srt_format_transcript.py::TestSRTFormatBasics::test_format_transcript_word_grouping_six_words_per_line PASSED [ 63%]
tests/test_srt_format_transcript.py::TestSRTFormatBasics::test_format_transcript_line_breaks_at_punctuation PASSED [ 63%]
tests/test_srt_format_transcript.py::TestSRTFormatBasics::test_empty_transcript_handled_gracefully PASSED [ 63%]
tests/test_srt_format_transcript.py::TestSRTFormatBasics::test_transcript_with_no_words_handled PASSED [ 64%]
tests/test_srt_format_transcript.py::TestSRTFormatAdvanced::test_transcript_formatting_for_ai_analysis PASSED [ 64%]
tests/test_srt_format_transcript.py::TestSRTFormatAdvanced::test_timestamps_match_word_timing_from_parakeet_mlx PASSED [ 64%]
tests/test_srt_format_transcript.py::TestSRTFormatAdvanced::test_formatted_transcript_sent_to_ai_model PASSED [ 64%]
tests/test_srt_format_transcript.py::TestSRTFormatEdgeCases::test_transcript_with_very_short_words PASSED [ 64%]
tests/test_srt_format_transcript.py::TestSRTFormatEdgeCases::test_transcript_with_very_long_words PASSED [ 64%]
tests/test_srt_format_transcript.py::TestSRTFormatEdgeCases::test_transcript_with_multiple_punctuation_marks PASSED [ 65%]
tests/test_srt_format_transcript.py::TestSRTFormatEdgeCases::test_transcript_with_special_characters PASSED [ 65%]
tests/test_srt_format_transcript.py::TestSRTFormatEdgeCases::test_transcript_with_numbers PASSED [ 65%]
tests/test_srt_format_transcript.py::TestSRTFormatEdgeCases::test_transcript_with_single_word PASSED [ 65%]
tests/test_srt_format_transcript.py::TestSRTFormatEdgeCases::test_transcript_very_long_duration PASSED [ 65%]
tests/test_srt_format_transcript.py::TestSRTFormatParameterization::test_format_with_custom_words_per_line PASSED [ 66%]
tests/test_srt_format_transcript.py::TestSRTFormatParameterization::test_format_consistency_same_input_same_output PASSED [ 66%]
tests/test_video_processing.py::TestVideoModuleImports::test_video_utils_imports PASSED [ 66%]
tests/test_video_processing.py::TestVideoModuleImports::test_ai_module_imports PASSED [ 66%]
tests/test_video_processing.py::TestVideoModuleImports::test_transcription_mlx_imports PASSED [ 66%]
tests/test_video_processing.py::TestVideoFileHandling::test_sample_video_exists PASSED [ 66%]
tests/test_video_processing.py::TestVideoFileHandling::test_sample_video_has_content PASSED [ 67%]
tests/test_video_processing.py::TestVideoFileHandling::test_video_in_correct_directory PASSED [ 67%]
tests/test_video_processing.py::TestVideoFileHandling::test_multiple_videos_supported PASSED [ 67%]
tests/test_video_processing.py::TestVideoFileHandling::test_video_naming_flexibility PASSED [ 67%]
tests/test_video_processing.py::TestClipGeneration::test_generated_clip_storage PASSED [ 67%]
tests/test_video_processing.py::TestClipGeneration::test_multiple_clips_per_task PASSED [ 68%]
tests/test_video_processing.py::TestClipGeneration::test_clip_duration_validation PASSED [ 68%]
tests/test_video_processing.py::TestClipGeneration::test_clip_time_format PASSED [ 68%]
tests/test_video_processing.py::TestSubtitleHandling::test_clip_has_transcript_text PASSED [ 68%]
tests/test_video_processing.py::TestSubtitleHandling::test_word_level_timestamps_storage PASSED [ 68%]
tests/test_video_processing.py::TestSubtitleHandling::test_subtitle_positioning_lower_middle PASSED [ 68%]
tests/test_video_processing.py::TestClipQualityMetrics::test_relevance_score_storage PASSED [ 69%]
tests/test_video_processing.py::TestClipQualityMetrics::test_reasoning_field_storage PASSED [ 69%]
tests/test_video_processing.py::TestVideoProcessingConfig::test_max_video_duration_setting PASSED [ 69%]
tests/test_video_processing.py::TestVideoProcessingConfig::test_clip_duration_setting PASSED [ 69%]
tests/test_video_processing.py::TestVideoProcessingConfig::test_max_clips_setting PASSED [ 69%]
tests/test_video_processing.py::TestVideoProcessingErrorHandling::test_missing_video_file_handling PASSED [ 70%]
tests/test_video_processing.py::TestVideoProcessingErrorHandling::test_invalid_clip_time_handling PASSED [ 70%]
tests/test_video_processing.py::TestVideoProcessingIntegration::test_complete_clip_workflow PASSED [ 70%]
tests/test_video_processing_endpoints.py::TestPostStartEndpoint::test_start_missing_source_url_returns_400 PASSED [ 70%]
tests/test_video_processing_endpoints.py::TestPostStartEndpoint::test_start_missing_user_id_returns_401 PASSED [ 70%]
tests/test_video_processing_endpoints.py::TestPostStartEndpoint::test_start_with_valid_youtube_url PASSED [ 70%]
tests/test_video_processing_endpoints.py::TestPostStartEndpoint::test_start_with_custom_fonts PASSED [ 71%]
tests/test_video_processing_endpoints.py::TestPostStartEndpoint::test_start_with_logo_overlay PASSED [ 71%]
tests/test_video_processing_endpoints.py::TestPostStartEndpoint::test_start_with_custom_ai_prompt PASSED [ 71%]
tests/test_video_processing_endpoints.py::TestPostStartEndpoint::test_start_with_dynamic_clip_lengths PASSED [ 71%]
tests/test_video_processing_endpoints.py::TestPostStartEndpoint::test_start_invalid_video_rejected PASSED [ 71%]
tests/test_video_processing_endpoints.py::TestPostStartWithProgressEndpoint::test_start_with_progress_returns_task_id PASSED [ 72%]
tests/test_video_processing_endpoints.py::TestPostStartWithProgressEndpoint::test_start_with_progress_initiates_background_processing PASSED [ 72%]
tests/test_video_processing_endpoints.py::TestPostStartWithProgressEndpoint::test_start_with_progress_task_status_updates PASSED [ 72%]
tests/test_video_processing_endpoints.py::TestPostStartWithProgressEndpoint::test_start_with_progress_logo_applied PASSED [ 72%]
tests/test_video_processing_endpoints.py::TestGetTaskDetailsEndpoint::test_get_task_returns_valid_task PASSED [ 72%]
tests/test_video_processing_endpoints.py::TestGetTaskDetailsEndpoint::test_get_task_returns_404_for_invalid_task PASSED [ 72%]
tests/test_video_processing_endpoints.py::TestGetTaskDetailsEndpoint::test_get_task_returns_task_status PASSED [ 73%]
tests/test_video_processing_endpoints.py::TestGetTaskDetailsEndpoint::test_get_task_returns_clip_count PASSED [ 73%]
tests/test_video_processing_endpoints.py::TestGetTaskDetailsEndpoint::test_get_task_returns_all_clips_metadata PASSED [ 73%]
tests/test_video_processing_endpoints.py::TestGetTaskClipsEndpoint::test_get_task_clips_returns_all_clips PASSED [ 73%]
tests/test_video_processing_endpoints.py::TestGetTaskClipsEndpoint::test_get_task_clips_includes_metadata PASSED [ 73%]
tests/test_video_processing_endpoints.py::TestGetTaskClipsEndpoint::test_get_task_clips_includes_relevance_scores PASSED [ 74%]
tests/test_video_processing_endpoints.py::TestGetTaskClipsEndpoint::test_get_task_clips_invalid_task_returns_404 PASSED [ 74%]
tests/test_video_processing_endpoints.py::TestGetTaskClipsEndpoint::test_get_task_clips_empty_task_returns_empty_array PASSED [ 74%]
tests/test_video_processing_parameters.py::test_video_processing_with_parameters PASSED [ 74%]
tests/unit/test_ai_output_validation.py::TestZeroSegmentsValidation::test_all_segments_rejected_raises_error PASSED [ 74%]
tests/unit/test_ai_output_validation.py::TestZeroSegmentsValidation::test_zero_segments_error_message_helpful PASSED [ 74%]
tests/unit/test_ai_output_validation.py::TestSegmentRejectionLogging::test_insufficient_text_logged PASSED [ 75%]
tests/unit/test_ai_output_validation.py::TestSegmentRejectionLogging::test_too_short_segment_logged PASSED [ 75%]
tests/unit/test_ai_output_validation.py::TestValidSegmentsAccepted::test_valid_segment_accepted PASSED [ 75%]
tests/unit/test_ai_output_validation.py::TestValidSegmentsAccepted::test_multiple_valid_segments_accepted PASSED [ 75%]
tests/unit/test_ai_output_validation.py::TestGroqResponseValidation::test_ultra_short_response_detected PASSED [ 75%]
tests/unit/test_dependencies.py::TestGetCurrentUser::test_get_current_user_with_x_user_id_header PASSED [ 76%]
tests/unit/test_dependencies.py::TestGetCurrentUser::test_get_current_user_with_user_id_header PASSED [ 76%]
tests/unit/test_dependencies.py::TestGetCurrentUser::test_get_current_user_prefers_x_user_id PASSED [ 76%]
tests/unit/test_dependencies.py::TestGetCurrentUser::test_get_current_user_missing_header_raises_401 PASSED [ 76%]
tests/unit/test_dependencies.py::TestGetCurrentUser::test_get_current_user_empty_header_raises_401 PASSED [ 76%]
tests/unit/test_dependencies.py::TestGetCurrentUser::test_get_current_user_whitespace_only_header_raises_401 PASSED [ 76%]
tests/unit/test_dependencies.py::TestGetCurrentUser::test_get_current_user_not_found_in_db_raises_401 PASSED [ 77%]
tests/unit/test_dependencies.py::TestGetCurrentUser::test_get_current_user_database_error_raises_500 PASSED [ 77%]
tests/unit/test_dependencies.py::TestGetCurrentUser::test_get_current_user_verifies_in_database PASSED [ 77%]
tests/unit/test_dependencies.py::TestGetOptionalUser::test_get_optional_user_returns_user_when_authenticated PASSED [ 77%]
tests/unit/test_dependencies.py::TestGetOptionalUser::test_get_optional_user_returns_none_when_not_authenticated PASSED [ 77%]
tests/unit/test_dependencies.py::TestGetOptionalUser::test_get_optional_user_returns_none_when_user_not_found PASSED [ 78%]
tests/unit/test_dependencies.py::TestGetOptionalUser::test_get_optional_user_does_not_raise_on_missing_header PASSED [ 78%]
tests/unit/test_dependencies.py::TestGetOptionalUser::test_get_optional_user_does_not_raise_on_database_error PASSED [ 78%]
tests/unit/test_dependencies.py::TestGetOptionalUser::test_get_optional_user_with_both_header_formats PASSED [ 78%]
tests/unit/test_font_options.py::TestParseDefaultConstants::test_default_font_family PASSED [ 78%]
tests/unit/test_font_options.py::TestParseDefaultConstants::test_default_font_size PASSED [ 78%]
tests/unit/test_font_options.py::TestParseDefaultConstants::test_default_font_color PASSED [ 79%]
tests/unit/test_font_options.py::TestParseFontOptions::test_parse_font_options_with_all_options PASSED [ 79%]
tests/unit/test_font_options.py::TestParseFontOptions::test_parse_font_options_with_partial_options PASSED [ 79%]
tests/unit/test_font_options.py::TestParseFontOptions::test_parse_font_options_with_no_options PASSED [ 79%]
tests/unit/test_font_options.py::TestParseFontOptions::test_parse_font_options_with_empty_font_options PASSED [ 79%]
tests/unit/test_font_options.py::TestParseFontOptions::test_parse_font_options_returns_dict PASSED [ 80%]
tests/unit/test_font_options.py::TestParseFontOptions::test_parse_font_options_font_size_override PASSED [ 80%]
tests/unit/test_font_options.py::TestParseFontOptions::test_parse_font_options_font_color_override PASSED [ 80%]
tests/unit/test_font_options.py::TestMergeWithDefaults::test_merge_with_defaults_request_overrides PASSED [ 80%]
tests/unit/test_font_options.py::TestMergeWithDefaults::test_merge_with_defaults_missing_in_request PASSED [ 80%]
tests/unit/test_font_options.py::TestMergeWithDefaults::test_merge_with_defaults_ignores_none_in_request PASSED [ 80%]
tests/unit/test_font_options.py::TestMergeWithDefaults::test_merge_with_defaults_empty_request PASSED [ 81%]
tests/unit/test_font_options.py::TestMergeWithDefaults::test_merge_with_defaults_empty_defaults PASSED [ 81%]
tests/unit/test_font_options.py::TestMergeWithDefaults::test_merge_with_defaults_preserves_defaults_dict PASSED [ 81%]
tests/unit/test_font_options.py::TestMergeWithDefaults::test_merge_with_defaults_handles_extra_keys_in_request PASSED [ 81%]
tests/unit/test_font_options.py::TestMergeWithDefaults::test_merge_with_defaults_numeric_values PASSED [ 81%]
tests/unit/test_font_options.py::TestMergeWithDefaults::test_merge_with_defaults_empty_string_value PASSED [ 82%]
tests/unit/test_font_options.py::TestMergeWithDefaults::test_merge_with_defaults_returns_new_dict PASSED [ 82%]
tests/unit/test_logo_path_resolution.py::TestLogoPathResolution::test_get_logo_path_none_when_not_set PASSED [ 82%]
tests/unit/test_logo_path_resolution.py::TestLogoPathResolution::test_get_logo_path_none_when_empty PASSED [ 82%]
tests/unit/test_logo_path_resolution.py::TestLogoPathResolution::test_get_logo_path_absolute_path_unchanged PASSED [ 82%]
tests/unit/test_logo_path_resolution.py::TestLogoPathResolution::test_get_logo_path_relative_converted_to_absolute PASSED [ 82%]
tests/unit/test_logo_path_resolution.py::TestLogoPathResolution::test_get_logo_path_returns_none_for_nonexistent_file PASSED [ 83%]
tests/unit/test_logo_path_resolution.py::TestLogoPathInVideoUtils::test_logo_path_conversion_to_absolute PASSED [ 83%]
tests/unit/test_logo_path_resolution.py::TestLogoPathInVideoUtils::test_logo_path_string_to_path_conversion PASSED [ 83%]
tests/unit/test_logo_path_resolution.py::TestLogoPathEdgeCases::test_get_logo_path_with_spaces_in_path PASSED [ 83%]
tests/unit/test_logo_path_resolution.py::TestLogoPathEdgeCases::test_get_logo_path_with_special_characters PASSED [ 83%]
tests/unit/test_logo_path_resolution.py::TestLogoPathEdgeCases::test_missing_key_in_preferences PASSED [ 84%]
tests/unit/test_millisecond_timestamps.py::test_parse_timestamps_with_milliseconds PASSED [ 84%]
tests/unit/test_millisecond_timestamps.py::test_parse_timestamps_without_milliseconds PASSED [ 84%]
tests/unit/test_millisecond_timestamps.py::test_parse_timestamps_edge_cases PASSED [ 84%]
tests/unit/test_millisecond_timestamps.py::test_timestamp_segment_validation PASSED [ 84%]
tests/unit/test_refactored_ai_classes.py::TestCleanStartValidator::test_validate_clean_start_returns_tuple PASSED [ 84%]
tests/unit/test_refactored_ai_classes.py::TestCleanStartValidator::test_validate_allows_clean_starts PASSED [ 85%]
tests/unit/test_refactored_ai_classes.py::TestCleanStartValidator::test_validate_rejects_forbidden_starts PASSED [ 85%]
tests/unit/test_refactored_ai_classes.py::TestCleanStartValidator::test_validate_case_insensitive PASSED [ 85%]
tests/unit/test_refactored_ai_classes.py::TestCleanStartValidator::test_validate_whitespace_handling PASSED [ 85%]
tests/unit/test_refactored_ai_classes.py::TestCleanStartValidator::test_validate_partial_matches_not_rejected PASSED [ 85%]
tests/unit/test_refactored_ai_classes.py::TestCleanStartValidator::test_forbidden_starts_constant PASSED [ 86%]
tests/unit/test_refactored_ai_classes.py::TestTimestampParser::test_parse_timestamp_valid_format PASSED [ 86%]
tests/unit/test_refactored_ai_classes.py::TestTimestampParser::test_parse_timestamp_invalid_format_raises_error PASSED [ 86%]
tests/unit/test_refactored_ai_classes.py::TestTimestampParser::test_calculate_duration_basic PASSED [ 86%]
tests/unit/test_refactored_ai_classes.py::TestTimestampParser::test_calculate_duration_invalid_timestamps PASSED [ 86%]
tests/unit/test_refactored_ai_classes.py::TestTimestampParser::test_validate_duration_positive_duration PASSED [ 86%]
tests/unit/test_refactored_ai_classes.py::TestTimestampParser::test_validate_duration_minimum_requirement PASSED [ 87%]
tests/unit/test_refactored_ai_classes.py::TestTimestampParser::test_min_duration_seconds_constant PASSED [ 87%]
tests/unit/test_refactored_ai_classes.py::TestTranscriptSegmentValidator::test_validate_text_content_valid PASSED [ 87%]
tests/unit/test_refactored_ai_classes.py::TestTranscriptSegmentValidator::test_validate_text_content_empty PASSED [ 87%]
tests/unit/test_refactored_ai_classes.py::TestTranscriptSegmentValidator::test_validate_text_content_whitespace_only PASSED [ 87%]
tests/unit/test_refactored_ai_classes.py::TestTranscriptSegmentValidator::test_validate_text_content_too_few_words PASSED [ 88%]
tests/unit/test_refactored_ai_classes.py::TestTranscriptSegmentValidator::test_validate_timestamps_valid_segment PASSED [ 88%]
tests/unit/test_refactored_ai_classes.py::TestTranscriptSegmentValidator::test_validate_timestamps_identical_times PASSED [ 88%]
tests/unit/test_refactored_ai_classes.py::TestTranscriptSegmentValidator::test_validate_timestamps_too_short PASSED [ 88%]
tests/unit/test_refactored_ai_classes.py::TestTranscriptSegmentValidator::test_validate_segment_comprehensive PASSED [ 88%]
tests/unit/test_refactored_ai_classes.py::TestTranscriptSegmentValidator::test_validate_segment_with_forbidden_start PASSED [ 88%]
tests/unit/test_refactored_ai_classes.py::TestTranscriptSegmentValidator::test_validate_segment_empty_text PASSED [ 89%]
tests/unit/test_refactored_ai_classes.py::TestTranscriptSegmentValidator::test_min_word_count_constant PASSED [ 89%]
tests/unit/test_timestamp_validators.py::TestTimestampParser::test_parse_timestamp_with_milliseconds PASSED [ 89%]
tests/unit/test_timestamp_validators.py::TestTimestampParser::test_parse_timestamp_without_milliseconds PASSED [ 89%]
tests/unit/test_timestamp_validators.py::TestTimestampParser::test_parse_timestamp_zero_minutes PASSED [ 89%]
tests/unit/test_timestamp_validators.py::TestTimestampParser::test_parse_timestamp_large_minutes PASSED [ 90%]
tests/unit/test_timestamp_validators.py::TestTimestampParser::test_parse_timestamp_invalid_format PASSED [ 90%]
tests/unit/test_timestamp_validators.py::TestTimestampParser::test_parse_timestamp_empty_string PASSED [ 90%]
tests/unit/test_timestamp_validators.py::TestTimestampParser::test_calculate_duration_with_milliseconds PASSED [ 90%]
tests/unit/test_timestamp_validators.py::TestTimestampParser::test_calculate_duration_negative PASSED [ 90%]
tests/unit/test_timestamp_validators.py::TestTimestampParser::test_validate_duration_valid PASSED [ 90%]
tests/unit/test_timestamp_validators.py::TestTimestampParser::test_validate_duration_too_short PASSED [ 91%]
tests/unit/test_timestamp_validators.py::TestTimestampParser::test_validate_duration_zero PASSED [ 91%]
tests/unit/test_timestamp_validators.py::TestTimestampParser::test_validate_duration_negative PASSED [ 91%]
tests/unit/test_timestamp_validators.py::TestTimestampFormatValidator::test_validate_precise_format PASSED [ 91%]
tests/unit/test_timestamp_validators.py::TestTimestampFormatValidator::test_validate_precise_format_single_digit_minute PASSED [ 91%]
tests/unit/test_timestamp_validators.py::TestTimestampFormatValidator::test_validate_imprecise_format PASSED [ 92%]
tests/unit/test_timestamp_validators.py::TestTimestampFormatValidator::test_validate_invalid_format PASSED [ 92%]
tests/unit/test_timestamp_validators.py::TestTimestampFormatValidator::test_validate_with_whitespace PASSED [ 92%]
tests/unit/test_timestamp_validators.py::TestTimestampFormatValidator::test_add_default_milliseconds_imprecise PASSED [ 92%]
tests/unit/test_timestamp_validators.py::TestTimestampFormatValidator::test_add_default_milliseconds_precise PASSED [ 92%]
tests/unit/test_timestamp_validators.py::TestTimestampFormatValidator::test_add_default_milliseconds_with_whitespace PASSED [ 92%]
tests/unit/test_timestamp_validators.py::TestTimestampIntegration::test_full_validation_flow PASSED [ 93%]
tests/unit/test_timestamp_validators.py::TestTimestampIntegration::test_fallback_flow_for_imprecise_timestamps PASSED [ 93%]
tests/unit/test_user_preferences_service.py::TestUserPreferencesServiceInit::test_init_stores_db PASSED [ 93%]
tests/unit/test_user_preferences_service.py::TestUserPreferencesServiceInit::test_default_preferences_are_defined PASSED [ 93%]
tests/unit/test_user_preferences_service.py::TestGetUserPreferences::test_get_user_preferences_returns_dict PASSED [ 93%]
tests/unit/test_user_preferences_service.py::TestGetUserPreferences::test_get_user_preferences_uses_defaults_for_none_values PASSED [ 94%]
tests/unit/test_user_preferences_service.py::TestGetUserPreferences::test_get_user_preferences_raises_for_missing_user PASSED [ 94%]
tests/unit/test_user_preferences_service.py::TestGetUserPreferences::test_get_user_preferences_merges_with_defaults PASSED [ 94%]
tests/unit/test_user_preferences_service.py::TestMergeWithRequestOptions::test_merge_with_request_options_request_overrides_user PASSED [ 94%]
tests/unit/test_user_preferences_service.py::TestMergeWithRequestOptions::test_merge_with_request_options_user_used_when_request_missing PASSED [ 94%]
tests/unit/test_user_preferences_service.py::TestMergeWithRequestOptions::test_merge_with_request_options_custom_ai_prompt PASSED [ 94%]
tests/unit/test_user_preferences_service.py::TestMergeWithRequestOptions::test_merge_clip_length_settings PASSED [ 95%]
tests/unit/test_user_preferences_service.py::TestGetLogoPath::test_get_logo_path_returns_path_object PASSED [ 95%]
tests/unit/test_user_preferences_service.py::TestGetLogoPath::test_get_logo_path_returns_none_when_not_configured PASSED [ 95%]
tests/unit/test_user_preferences_service.py::TestGetLogoPath::test_get_logo_path_returns_none_for_empty_path PASSED [ 95%]
tests/unit/test_video_service_async.py::TestAsyncVideoServiceInit::test_init_stores_db_and_config PASSED [ 95%]
tests/unit/test_video_service_async.py::TestCreateTask::test_create_task_returns_task_id PASSED [ 96%]
tests/unit/test_video_service_async.py::TestCreateTask::test_create_task_creates_source_and_task PASSED [ 96%]
tests/unit/test_video_service_async.py::TestCreateTask::test_create_task_sets_processing_status PASSED [ 96%]
tests/unit/test_video_service_async.py::TestCreateTask::test_create_task_with_custom_font_options PASSED [ 96%]
tests/unit/test_video_service_async.py::TestProcessVideoAsync::test_process_video_async_updates_task_status PASSED [ 96%]
tests/unit/test_video_service_async.py::TestProcessVideoAsync::test_process_video_async_returns_none PASSED [ 96%]
tests/unit/test_video_service_async.py::TestUpdateTaskStatus::test_update_task_status_executes_update PASSED [ 97%]
tests/unit/test_video_service_async.py::TestUpdateTaskStatus::test_update_task_status_different_statuses PASSED [ 97%]
tests/unit/test_video_service_async.py::TestProcessVideoAsyncErrorHandling::test_process_video_async_marks_error_on_failure PASSED [ 97%]
tests/unit/test_video_utils_timestamps.py::TestParseTimestampMMSSFormat::test_parse_mm_ss_integer_seconds PASSED [ 97%]
tests/unit/test_video_utils_timestamps.py::TestParseTimestampMMSSFormat::test_parse_mm_ss_with_milliseconds PASSED [ 97%]
tests/unit/test_video_utils_timestamps.py::TestParseTimestampMMSSFormat::test_parse_mm_ss_milliseconds_edge_cases PASSED [ 98%]
tests/unit/test_video_utils_timestamps.py::TestParseTimestampHHMMSSFormat::test_parse_hh_mm_ss_integer_seconds PASSED [ 98%]
tests/unit/test_video_utils_timestamps.py::TestParseTimestampHHMMSSFormat::test_parse_hh_mm_ss_with_milliseconds PASSED [ 98%]
tests/unit/test_video_utils_timestamps.py::TestParseTimestampHHMMSSFormat::test_parse_hh_mm_ss_milliseconds_edge_cases PASSED [ 98%]
tests/unit/test_video_utils_timestamps.py::TestParseTimestampPureSeconds::test_parse_pure_float_seconds PASSED [ 98%]
tests/unit/test_video_utils_timestamps.py::TestParseTimestampPureSeconds::test_parse_pure_integer_seconds PASSED [ 98%]
tests/unit/test_video_utils_timestamps.py::TestParseTimestampWhitespace::test_strip_whitespace PASSED [ 99%]
tests/unit/test_video_utils_timestamps.py::TestParseTimestampErrorHandling::test_invalid_format_returns_zero PASSED [ 99%]
tests/unit/test_video_utils_timestamps.py::TestParseTimestampErrorHandling::test_malformed_timestamps PASSED [ 99%]
tests/unit/test_video_utils_timestamps.py::TestIntegrationWithVideoProcessing::test_segment_duration_calculation PASSED [ 99%]
tests/unit/test_video_utils_timestamps.py::TestIntegrationWithVideoProcessing::test_multiple_clips_timestamp_sequence PASSED [ 99%]
tests/unit/test_video_utils_timestamps.py::TestIntegrationWithVideoProcessing::test_backward_compatibility_with_old_formats PASSED [100%]Running teardown with pytest sessionfinish...


=================================== FAILURES ===================================
_______ TestLogoPathHandling.test_logo_path_extraction_from_preferences ________
tests/integration/test_service_integration.py:263: in test_logo_path_extraction_from_preferences
    assert logo_path is not None
E   assert None is not None
----------------------------- Captured stderr call -----------------------------
2025-12-17 19:40:53 - src.services.user_preferences_service - WARNING - 🟡 Logo file not found at path: /path/to/logo.png
------------------------------ Captured log call -------------------------------
WARNING  src.services.user_preferences_service:user_preferences_service.py:203 🟡 Logo file not found at path: /path/to/logo.png
_________________ test_task_status_update_with_progress_fails __________________
tests/repositories/test_task_repository_schema.py:107: in test_task_status_update_with_progress_fails
    with pytest.raises(OperationalError) as exc_info:
E   Failed: DID NOT RAISE <class 'sqlalchemy.exc.OperationalError'>
----------------------------- Captured stderr call -----------------------------
2025-12-17 19:40:53 - src.repositories.task_repository - INFO - 🟢 Created task a3f3afb9-8557-4403-84ec-dbc1223194b0 for user e84a18f6-e889-426f-b700-7e18bfcdef28
2025-12-17 19:40:53 - src.repositories.task_repository - INFO - 🟢 Updated task a3f3afb9-8557-4403-84ec-dbc1223194b0 status to processing
------------------------------ Captured log call -------------------------------
INFO     src.repositories.task_repository:task_repository.py:68 🟢 Created task a3f3afb9-8557-4403-84ec-dbc1223194b0 for user e84a18f6-e889-426f-b700-7e18bfcdef28
INFO     src.repositories.task_repository:task_repository.py:139 🟢 Updated task a3f3afb9-8557-4403-84ec-dbc1223194b0 status to processing
___________ test_task_status_update_with_progress_message_only_fails ___________
tests/repositories/test_task_repository_schema.py:144: in test_task_status_update_with_progress_message_only_fails
    with pytest.raises(OperationalError) as exc_info:
E   Failed: DID NOT RAISE <class 'sqlalchemy.exc.OperationalError'>
----------------------------- Captured stderr call -----------------------------
2025-12-17 19:40:53 - src.repositories.task_repository - INFO - 🟢 Created task 25e56026-fe08-4bb8-8584-b065e701c10c for user 089e56ad-b54d-4f3a-b6d8-b5300df75cb9
2025-12-17 19:40:53 - src.repositories.task_repository - INFO - 🟢 Updated task 25e56026-fe08-4bb8-8584-b065e701c10c status to error
------------------------------ Captured log call -------------------------------
INFO     src.repositories.task_repository:task_repository.py:68 🟢 Created task 25e56026-fe08-4bb8-8584-b065e701c10c for user 089e56ad-b54d-4f3a-b6d8-b5300df75cb9
INFO     src.repositories.task_repository:task_repository.py:139 🟢 Updated task 25e56026-fe08-4bb8-8584-b065e701c10c status to error
________ test_task_get_with_progress_gracefully_handles_missing_columns ________
tests/repositories/test_task_repository_schema.py:184: in test_task_get_with_progress_gracefully_handles_missing_columns
    assert task["progress"] is None, "Should gracefully return None for missing progress"
E   AssertionError: Should gracefully return None for missing progress
E   assert 0 is None
----------------------------- Captured stderr call -----------------------------
2025-12-17 19:40:53 - src.repositories.task_repository - INFO - 🟢 Created task 515ff5db-536f-4a8b-8fc1-c3dad76d3cac for user bcfc1ea0-3e3c-415e-a2b0-31591ac747bb
------------------------------ Captured log call -------------------------------
INFO     src.repositories.task_repository:task_repository.py:68 🟢 Created task 515ff5db-536f-4a8b-8fc1-c3dad76d3cac for user bcfc1ea0-3e3c-415e-a2b0-31591ac747bb
_________________ test_connection_cleanup_after_failed_update __________________
tests/repositories/test_task_repository_schema.py:223: in test_connection_cleanup_after_failed_update
    assert task["status"] == "queued", "Status should be unchanged"
E   AssertionError: Status should be unchanged
E   assert 'processing' == 'queued'
E     
E     - queued
E     + processing
----------------------------- Captured stderr call -----------------------------
2025-12-17 19:40:53 - src.repositories.task_repository - INFO - 🟢 Created task 0f5ea123-d63c-41a0-bf57-e2a45d307dbd for user 00d8fde7-6474-4a78-a7f0-f764a5e066a4
2025-12-17 19:40:53 - src.repositories.task_repository - INFO - 🟢 Updated task 0f5ea123-d63c-41a0-bf57-e2a45d307dbd status to processing
2025-12-17 19:40:53 - src.repositories.task_repository - INFO - 🟢 Updated task 0f5ea123-d63c-41a0-bf57-e2a45d307dbd status to processing (progress: 10%)
2025-12-17 19:40:53 - src.repositories.task_repository - INFO - 🟢 Updated task 0f5ea123-d63c-41a0-bf57-e2a45d307dbd status to processing (progress: 20%)
2025-12-17 19:40:53 - src.repositories.task_repository - INFO - 🟢 Updated task 0f5ea123-d63c-41a0-bf57-e2a45d307dbd status to processing (progress: 30%)
2025-12-17 19:40:53 - src.repositories.task_repository - INFO - 🟢 Updated task 0f5ea123-d63c-41a0-bf57-e2a45d307dbd status to processing (progress: 40%)
------------------------------ Captured log call -------------------------------
INFO     src.repositories.task_repository:task_repository.py:68 🟢 Created task 0f5ea123-d63c-41a0-bf57-e2a45d307dbd for user 00d8fde7-6474-4a78-a7f0-f764a5e066a4
INFO     src.repositories.task_repository:task_repository.py:139 🟢 Updated task 0f5ea123-d63c-41a0-bf57-e2a45d307dbd status to processing
INFO     src.repositories.task_repository:task_repository.py:139 🟢 Updated task 0f5ea123-d63c-41a0-bf57-e2a45d307dbd status to processing (progress: 10%)
INFO     src.repositories.task_repository:task_repository.py:139 🟢 Updated task 0f5ea123-d63c-41a0-bf57-e2a45d307dbd status to processing (progress: 20%)
INFO     src.repositories.task_repository:task_repository.py:139 🟢 Updated task 0f5ea123-d63c-41a0-bf57-e2a45d307dbd status to processing (progress: 30%)
INFO     src.repositories.task_repository:task_repository.py:139 🟢 Updated task 0f5ea123-d63c-41a0-bf57-e2a45d307dbd status to processing (progress: 40%)
____________ TestRootEndpoint.test_root_endpoint_response_structure ____________
tests/test_api_endpoints.py:30: in test_root_endpoint_response_structure
    assert field in data, f"Missing field: {field}"
E   AssertionError: Missing field: name
E   assert 'name' in {'message': 'This is the SupoClip FastAPI-based API. Visit /docs for the API documentation.'}
----------------------------- Captured stderr call -----------------------------
2025-12-17 19:40:53 - httpx - INFO - 🟢 HTTP Request: GET http://testserver/ "HTTP/1.1 200 OK"
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1025 🟢 HTTP Request: GET http://testserver/ "HTTP/1.1 200 OK"
__________________ TestRootEndpoint.test_root_endpoint_values __________________
tests/test_api_endpoints.py:37: in test_root_endpoint_values
    assert data["name"] == "SupoClip API"
           ^^^^^^^^^^^^
E   KeyError: 'name'
----------------------------- Captured stderr call -----------------------------
2025-12-17 19:40:53 - httpx - INFO - 🟢 HTTP Request: GET http://testserver/ "HTTP/1.1 200 OK"
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1025 🟢 HTTP Request: GET http://testserver/ "HTTP/1.1 200 OK"
_______ TestHealthCheckEndpoints.test_redis_health_check_endpoint_exists _______
tests/test_api_endpoints.py:69: in test_redis_health_check_endpoint_exists
    assert response.status_code in [200, 500, 503]
E   assert 404 in [200, 500, 503]
E    +  where 404 = <Response [404 Not Found]>.status_code
----------------------------- Captured stderr call -----------------------------
2025-12-17 19:40:54 - httpx - INFO - 🟢 HTTP Request: GET http://testserver/health/redis "HTTP/1.1 404 Not Found"
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1025 🟢 HTTP Request: GET http://testserver/health/redis "HTTP/1.1 404 Not Found"
_______________ TestConfigLoading.test_mlx_whisper_model_default _______________
tests/test_configuration.py:33: in test_mlx_whisper_model_default
    assert config.mlx_whisper_model == "medium"
           ^^^^^^^^^^^^^^^^^^^^^^^^
E   AttributeError: 'Config' object has no attribute 'mlx_whisper_model'
______________ TestConfigLoading.test_mlx_whisper_model_from_env _______________
tests/test_configuration.py:39: in test_mlx_whisper_model_from_env
    assert config.mlx_whisper_model == "large"
           ^^^^^^^^^^^^^^^^^^^^^^^^
E   AttributeError: 'Config' object has no attribute 'mlx_whisper_model'
___________ TestOfflineCapability.test_mlx_whisper_available_offline ___________
tests/test_configuration.py:261: in test_mlx_whisper_available_offline
    assert config.mlx_whisper_model == "tiny"
           ^^^^^^^^^^^^^^^^^^^^^^^^
E   AttributeError: 'Config' object has no attribute 'mlx_whisper_model'
____________ TestE2EVideoProcessingPipeline.test_api_root_endpoint _____________
tests/test_end_to_end.py:435: in test_api_root_endpoint
    assert field in data, f"Missing field: {field}"
E   AssertionError: Missing field: name
E   assert 'name' in {'message': 'This is the SupoClip FastAPI-based API. Visit /docs for the API documentation.'}
----------------------------- Captured stderr call -----------------------------
2025-12-17 19:40:56 - httpx - INFO - 🟢 HTTP Request: GET http://testserver/ "HTTP/1.1 200 OK"
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1025 🟢 HTTP Request: GET http://testserver/ "HTTP/1.1 200 OK"
________ TestE2EVideoProcessingPipeline.test_mlx_whisper_configuration _________
tests/test_end_to_end.py:469: in test_mlx_whisper_configuration
    assert e2e_config.mlx_whisper_model is not None
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   AttributeError: 'Config' object has no attribute 'mlx_whisper_model'
____ TestE2EVideoProcessingPipeline.test_performance_baseline_configuration ____
tests/test_end_to_end.py:543: in test_performance_baseline_configuration
    assert e2e_config.mlx_whisper_model is not None
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   AttributeError: 'Config' object has no attribute 'mlx_whisper_model'
________ TestE2EAPIEndpoints.test_task_creation_endpoint_requires_auth _________
tests/test_end_to_end.py:594: in test_task_creation_endpoint_requires_auth
    assert response.status_code in [200, 401, 422, 500]
E   assert 404 in [200, 401, 422, 500]
E    +  where 404 = <Response [404 Not Found]>.status_code
----------------------------- Captured stderr call -----------------------------
2025-12-17 19:40:56 - src.services.user_preferences_service - ERROR - 🛑 User local-user not found in database
2025-12-17 19:40:56 - httpx - INFO - 🟢 HTTP Request: POST http://testserver/tasks/ "HTTP/1.1 404 Not Found"
------------------------------ Captured log call -------------------------------
ERROR    src.services.user_preferences_service:user_preferences_service.py:109 🛑 User local-user not found in database
INFO     httpx:_client.py:1025 🟢 HTTP Request: POST http://testserver/tasks/ "HTTP/1.1 404 Not Found"
___________ TestE2ELocalFirstOperation.test_transcription_local_mlx ____________
tests/test_end_to_end.py:792: in test_transcription_local_mlx
    assert e2e_config.mlx_whisper_model is not None
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   AttributeError: 'Config' object has no attribute 'mlx_whisper_model'
_________________ test_groq_failure_falls_back_to_pydantic_ai __________________
tests/test_groq_fallback.py:86: in test_groq_failure_falls_back_to_pydantic_ai
    result = await get_most_relevant_parts_by_transcript(test_transcript)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
src/ai.py:399: in get_most_relevant_parts_by_transcript
    structured_result = await analyze_transcript_structured(
src/ai_structured.py:280: in analyze_transcript_structured
    completion = await client.chat.completions.create(
../../../../.pyenv/versions/3.11.12/lib/python3.11/unittest/mock.py:2240: in _execute_mock_call
    raise effect
E   Exception: 500 Internal Server Error from Groq API
----------------------------- Captured stderr call -----------------------------
2025-12-17 19:41:08 - src.ai - INFO - 🟢 Starting AI analysis of transcript (562 chars)
2025-12-17 19:41:08 - src.ai - INFO - 🟢 Clip length settings - Min: 10s, Max: 45s
2025-12-17 19:41:08 - src.ai - INFO - 🟢 Using Groq Structured Outputs API for Llama 4 Scout compatibility
2025-12-17 19:41:08 - src.ai_structured - INFO - 🟢 Analyzing transcript with Groq Structured Outputs (562 chars)
2025-12-17 19:41:08 - src.ai_structured - INFO - 🟢 Using model: meta-llama/llama-4-scout-17b-16e-instruct
2025-12-17 19:41:08 - src.ai_structured - INFO - 🟢 Clip length settings - Min: 10s, Max: 45s
2025-12-17 19:41:08 - src.ai_structured - ERROR - 🛑 Error in Groq structured analysis: 500 Internal Server Error from Groq API
2025-12-17 19:41:08 - src.ai - ERROR - 🛑 Groq Structured Outputs API error: 500 Internal Server Error from Groq API
2025-12-17 19:41:08 - src.ai - ERROR - 🛑 Error in transcript analysis: 500 Internal Server Error from Groq API
Traceback (most recent call last):
  File "/Users/cspenn/Documents/github/supoclip/backend/src/ai.py", line 399, in get_most_relevant_parts_by_transcript
    structured_result = await analyze_transcript_structured(
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py", line 280, in analyze_transcript_structured
    completion = await client.chat.completions.create(
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/cspenn/.pyenv/versions/3.11.12/lib/python3.11/unittest/mock.py", line 2240, in _execute_mock_call
    raise effect
Exception: 500 Internal Server Error from Groq API
------------------------------ Captured log call -------------------------------
INFO     src.ai:ai.py:351 🟢 Starting AI analysis of transcript (562 chars)
INFO     src.ai:ai.py:352 🟢 Clip length settings - Min: 10s, Max: 45s
INFO     src.ai:ai.py:392 🟢 Using Groq Structured Outputs API for Llama 4 Scout compatibility
INFO     src.ai_structured:ai_structured.py:252 🟢 Analyzing transcript with Groq Structured Outputs (562 chars)
INFO     src.ai_structured:ai_structured.py:255 🟢 Using model: meta-llama/llama-4-scout-17b-16e-instruct
INFO     src.ai_structured:ai_structured.py:256 🟢 Clip length settings - Min: 10s, Max: 45s
ERROR    src.ai_structured:ai_structured.py:501 🛑 Error in Groq structured analysis: 500 Internal Server Error from Groq API
ERROR    src.ai:ai.py:428 🛑 Groq Structured Outputs API error: 500 Internal Server Error from Groq API
ERROR    src.ai:ai.py:480 🛑 Error in transcript analysis: 500 Internal Server Error from Groq API
Traceback (most recent call last):
  File "/Users/cspenn/Documents/github/supoclip/backend/src/ai.py", line 399, in get_most_relevant_parts_by_transcript
    structured_result = await analyze_transcript_structured(
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/cspenn/Documents/github/supoclip/backend/src/ai_structured.py", line 280, in analyze_transcript_structured
    completion = await client.chat.completions.create(
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/cspenn/.pyenv/versions/3.11.12/lib/python3.11/unittest/mock.py", line 2240, in _execute_mock_call
    raise effect
Exception: 500 Internal Server Error from Groq API
_ TestCloudAPIKeyDetection.test_has_cloud_api_key_returns_false_when_all_empty _
tests/test_local_llm_config.py:177: in test_has_cloud_api_key_returns_false_when_all_empty
    assert config._has_cloud_api_key() is False
E   assert True is False
E    +  where True = _has_cloud_api_key()
E    +    where _has_cloud_api_key = <src.config.Config object at 0x38229ef90>._has_cloud_api_key
______ TestLogoParameterPassing.test_logo_params_passed_to_clip_creation _______
tests/test_logo_pipeline.py:103: in test_logo_params_passed_to_clip_creation
    with patch(
../../../../.pyenv/versions/3.11.12/lib/python3.11/unittest/mock.py:1446: in __enter__
    original, local = self.get_original()
                      ^^^^^^^^^^^^^^^^^^^
../../../../.pyenv/versions/3.11.12/lib/python3.11/unittest/mock.py:1419: in get_original
    raise AttributeError(
E   AttributeError: <module 'src.services.video_service' from '/Users/cspenn/Documents/github/supoclip/backend/src/services/video_service.py'> does not have the attribute 'analyze_transcript_for_clips'
___________ TestLogoParameterPassing.test_logo_overlay_code_executes ___________
tests/test_logo_pipeline.py:217: in test_logo_overlay_code_executes
    with patch("src.video_utils.VideoFileClip") as mock_video, patch(
../../../../.pyenv/versions/3.11.12/lib/python3.11/unittest/mock.py:1446: in __enter__
    original, local = self.get_original()
                      ^^^^^^^^^^^^^^^^^^^
../../../../.pyenv/versions/3.11.12/lib/python3.11/unittest/mock.py:1419: in get_original
    raise AttributeError(
E   AttributeError: <module 'src.video_utils' from '/Users/cspenn/Documents/github/supoclip/backend/src/video_utils.py'> does not have the attribute 'ImageClip'
________________________ test_logo_overlay_code_exists _________________________
tests/test_logo_pipeline.py:295: in test_logo_overlay_code_exists
    content = video_utils_path.read_text()
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../../../.pyenv/versions/3.11.12/lib/python3.11/pathlib.py:1058: in read_text
    with self.open(mode='r', encoding=encoding, errors=errors) as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../../../.pyenv/versions/3.11.12/lib/python3.11/pathlib.py:1044: in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   FileNotFoundError: [Errno 2] No such file or directory: '/Users/cspenn/Documents/github/supoclip/backend/tests/src/video_utils.py'
___________ TestLogoUploadEndpoint.test_logo_upload_accepts_png_file ___________
tests/test_logo_upload_feature.py:59: in test_logo_upload_accepts_png_file
    assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
E   AssertionError: Expected 200/201, got 401: {"detail":"User not found"}
E   assert 401 in [200, 201]
E    +  where 401 = <Response [401 Unauthorized]>.status_code
----------------------------- Captured stderr call -----------------------------
2025-12-17 19:41:11 - src.dependencies - WARNING - 🟡 Authentication attempt for non-existent user: test-user-1
2025-12-17 19:41:11 - httpx - INFO - 🟢 HTTP Request: POST http://testserver/upload-logo "HTTP/1.1 401 Unauthorized"
------------------------------ Captured log call -------------------------------
WARNING  src.dependencies:dependencies.py:77 🟡 Authentication attempt for non-existent user: test-user-1
INFO     httpx:_client.py:1025 🟢 HTTP Request: POST http://testserver/upload-logo "HTTP/1.1 401 Unauthorized"
___________ TestLogoUploadEndpoint.test_logo_upload_accepts_jpg_file ___________
tests/test_logo_upload_feature.py:77: in test_logo_upload_accepts_jpg_file
    assert response.status_code in [200, 201]
E   assert 401 in [200, 201]
E    +  where 401 = <Response [401 Unauthorized]>.status_code
----------------------------- Captured stderr call -----------------------------
2025-12-17 19:41:11 - src.dependencies - WARNING - 🟡 Authentication attempt for non-existent user: test-user-1
2025-12-17 19:41:11 - httpx - INFO - 🟢 HTTP Request: POST http://testserver/upload-logo "HTTP/1.1 401 Unauthorized"
------------------------------ Captured log call -------------------------------
WARNING  src.dependencies:dependencies.py:77 🟡 Authentication attempt for non-existent user: test-user-1
INFO     httpx:_client.py:1025 🟢 HTTP Request: POST http://testserver/upload-logo "HTTP/1.1 401 Unauthorized"
_______ TestLogoUploadEndpoint.test_logo_upload_rejects_non_image_files ________
tests/test_logo_upload_feature.py:91: in test_logo_upload_rejects_non_image_files
    assert response.status_code in [400, 415]
E   assert 401 in [400, 415]
E    +  where 401 = <Response [401 Unauthorized]>.status_code
----------------------------- Captured stderr call -----------------------------
2025-12-17 19:41:11 - src.dependencies - WARNING - 🟡 Authentication attempt for non-existent user: test-user-1
2025-12-17 19:41:11 - httpx - INFO - 🟢 HTTP Request: POST http://testserver/upload-logo "HTTP/1.1 401 Unauthorized"
------------------------------ Captured log call -------------------------------
WARNING  src.dependencies:dependencies.py:77 🟡 Authentication attempt for non-existent user: test-user-1
INFO     httpx:_client.py:1025 🟢 HTTP Request: POST http://testserver/upload-logo "HTTP/1.1 401 Unauthorized"
_______ TestLogoUploadEndpoint.test_logo_upload_missing_file_returns_400 _______
tests/test_logo_upload_feature.py:102: in test_logo_upload_missing_file_returns_400
    assert response.status_code == 400
E   assert 401 == 400
E    +  where 401 = <Response [401 Unauthorized]>.status_code
----------------------------- Captured stderr call -----------------------------
2025-12-17 19:41:11 - src.dependencies - WARNING - 🟡 Authentication attempt for non-existent user: test-user-1
2025-12-17 19:41:11 - httpx - INFO - 🟢 HTTP Request: POST http://testserver/upload-logo "HTTP/1.1 401 Unauthorized"
------------------------------ Captured log call -------------------------------
WARNING  src.dependencies:dependencies.py:77 🟡 Authentication attempt for non-existent user: test-user-1
INFO     httpx:_client.py:1025 🟢 HTTP Request: POST http://testserver/upload-logo "HTTP/1.1 401 Unauthorized"
________ TestLogoFileHandling.test_user_database_updated_with_logo_path ________
tests/test_logo_upload_feature.py:180: in test_user_database_updated_with_logo_path
    test_db_session.query(User).filter(User.id == "test-logo-db-user").update(
    ^^^^^^^^^^^^^^^^^^^^^
E   AttributeError: 'AsyncSession' object has no attribute 'query'
================================ tests coverage ================================
______________ coverage: platform darwin, python 3.11.12-final-0 _______________

Name                                       Stmts   Miss Branch BrPart  Cover
----------------------------------------------------------------------------
src/__init__.py                                0      0      0      0   100%
src/ai.py                                    193     49     56      8    72%
src/ai_structured.py                         155     60     40     12    53%
src/api/__init__.py                            0      0      0      0   100%
src/api/routes/__init__.py                     0      0      0      0   100%
src/api/routes/fonts.py                       56     18      6      1    66%
src/api/routes/media.py                       47     47      8      0     0%
src/api/routes/tasks.py                      177    123     42      3    26%
src/config.py                                 51      1      6      1    96%
src/database.py                               57     37     20      1    27%
src/dependencies.py                           41      1      6      0    98%
src/lifecycle.py                              49     32      0      0    35%
src/logging_config.py                         55     10     12      5    78%
src/main.py                                  218    135     32      2    35%
src/models.py                                 96      1      2      1    98%
src/repositories/__init__.py                   0      0      0      0   100%
src/repositories/clip_repository.py           42     16      4      1    59%
src/repositories/source_repository.py         30     19      2      0    34%
src/repositories/task_repository.py           61     17     10      3    69%
src/services/__init__.py                       0      0      0      0   100%
src/services/font_service.py                 211     97     50      7    52%
src/services/task_service.py                  65     41     12      0    31%
src/services/user_preferences_service.py      59      4     22      2    93%
src/services/video_service.py                134     41     30     13    66%
src/services/video_service_async.py           95     38     18      5    55%
src/transcription_mlx.py                     184    105     58     10    40%
src/utils/__init__.py                          0      0      0      0   100%
src/utils/async_helpers.py                    17      7      0      0    59%
src/utils/font_options.py                     13      0      4      0   100%
src/video_utils.py                           697    196    180     46    69%
src/workers/__init__.py                        0      0      0      0   100%
src/workers/job_queue.py                      39     23      8      0    34%
src/workers/local_progress.py                 64     41     16      0    29%
src/workers/local_queue.py                    89      6     12      1    91%
src/workers/tasks.py                          27     19      0      0    30%
src/youtube_utils.py                         140     59     42     12    52%
----------------------------------------------------------------------------
TOTAL                                       3162   1243    698    134    57%
Test tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_transcription_with_mlx_whisper was skipped. Reason: 
('/Users/cspenn/Documents/github/supoclip/backend/tests/test_end_to_end.py', 516, "Skipped: MLX Whisper transcription not available: 'Config' object has no attribute 
'mlx_whisper_model'")
Test tests/test_font_cutoff_and_short_clips.py::TestFontCutoffIssue::test_barlow_condensed_bold_cutoff_reproduction was skipped. Reason: 
('/Users/cspenn/Documents/github/supoclip/backend/tests/test_font_cutoff_and_short_clips.py', 93, 'Skipped: Font not found: 
/Users/cspenn/Documents/github/supoclip/backend/fonts/Barlow-Condensed-Bold.ttf')
Test tests/test_font_cutoff_and_short_clips.py::TestActualUserScenario::test_user_scenario_reproduction was skipped. Reason: 
('/Users/cspenn/Documents/github/supoclip/backend/tests/test_font_cutoff_and_short_clips.py', 360, "Skipped: API not available: cannot access local variable 'durations'
where it is not associated with a value")
Test tests/test_logo_pipeline.py::test_logo_file_exists was skipped. Reason: ('/Users/cspenn/Documents/github/supoclip/backend/tests/test_logo_pipeline.py', 284, 
'Skipped: Test logo file not found at /Users/cspenn/Documents/github/supoclip/backend/tests/docs/TI_Primary_2Color_Reverse.png')
=========================== short test summary info ============================
FAILED tests/integration/test_service_integration.py::TestLogoPathHandling::test_logo_path_extraction_from_preferences
FAILED tests/repositories/test_task_repository_schema.py::test_task_status_update_with_progress_fails
FAILED tests/repositories/test_task_repository_schema.py::test_task_status_update_with_progress_message_only_fails
FAILED tests/repositories/test_task_repository_schema.py::test_task_get_with_progress_gracefully_handles_missing_columns
FAILED tests/repositories/test_task_repository_schema.py::test_connection_cleanup_after_failed_update
FAILED tests/test_api_endpoints.py::TestRootEndpoint::test_root_endpoint_response_structure
FAILED tests/test_api_endpoints.py::TestRootEndpoint::test_root_endpoint_values
FAILED tests/test_api_endpoints.py::TestHealthCheckEndpoints::test_redis_health_check_endpoint_exists
FAILED tests/test_configuration.py::TestConfigLoading::test_mlx_whisper_model_default
FAILED tests/test_configuration.py::TestConfigLoading::test_mlx_whisper_model_from_env
FAILED tests/test_configuration.py::TestOfflineCapability::test_mlx_whisper_available_offline
FAILED tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_api_root_endpoint
FAILED tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_mlx_whisper_configuration
FAILED tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_performance_baseline_configuration
FAILED tests/test_end_to_end.py::TestE2EAPIEndpoints::test_task_creation_endpoint_requires_auth
FAILED tests/test_end_to_end.py::TestE2ELocalFirstOperation::test_transcription_local_mlx
FAILED tests/test_groq_fallback.py::test_groq_failure_falls_back_to_pydantic_ai
FAILED tests/test_local_llm_config.py::TestCloudAPIKeyDetection::test_has_cloud_api_key_returns_false_when_all_empty
FAILED tests/test_logo_pipeline.py::TestLogoParameterPassing::test_logo_params_passed_to_clip_creation
FAILED tests/test_logo_pipeline.py::TestLogoParameterPassing::test_logo_overlay_code_executes
FAILED tests/test_logo_pipeline.py::test_logo_overlay_code_exists - FileNotFo...
FAILED tests/test_logo_upload_feature.py::TestLogoUploadEndpoint::test_logo_upload_accepts_png_file
FAILED tests/test_logo_upload_feature.py::TestLogoUploadEndpoint::test_logo_upload_accepts_jpg_file
FAILED tests/test_logo_upload_feature.py::TestLogoUploadEndpoint::test_logo_upload_rejects_non_image_files
FAILED tests/test_logo_upload_feature.py::TestLogoUploadEndpoint::test_logo_upload_missing_file_returns_400
FAILED tests/test_logo_upload_feature.py::TestLogoFileHandling::test_user_database_updated_with_logo_path
====== 26 failed, 520 passed, 4 skipped, 11 warnings in 286.67s (0:04:46) ======
