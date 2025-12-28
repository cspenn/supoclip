src/video_utils.py
    C 948:0 SubtitleTextClipCreator - C
    M 960:4 SubtitleTextClipCreator.create_text_clip - C
    F 1196:0 create_optimized_clip - C
    F 34:0 resolve_font_path - B
    F 846:0 filter_face_outliers - B
    C 369:0 TranscriptLineBreaker - B
    M 376:4 TranscriptLineBreaker.should_break_line - B
    F 230:0 extract_text_from_cache - B
    F 456:0 format_transcript_for_ai - B
    M 589:4 MediaPipeFaceDetector.detect - B
    C 622:0 OpenCVDNNFaceDetector - B
    M 644:4 OpenCVDNNFaceDetector.detect - B
    C 712:0 VideoFrameSampler - B
    M 758:4 FaceDetectionService.detect_in_frame - B
    C 1066:0 SubtitleClipBuilder - B
    F 1524:0 create_clips_with_transitions - B
    C 312:0 FaceCenteredCropCalculator - B
    M 716:4 VideoFrameSampler.generate_sample_times - B
    C 916:0 SubtitleWordFilter - B
    M 1070:4 SubtitleClipBuilder.build_clips - B
    F 805:0 detect_faces_in_clip - A
    F 884:0 parse_timestamp_to_seconds - A
    F 1370:0 create_clips_from_segments - A
    M 316:4 FaceCenteredCropCalculator.calculate - A
    C 573:0 MediaPipeFaceDetector - A
    C 744:0 FaceDetectionService - A
    M 920:4 SubtitleWordFilter.get_relevant_words - A
    F 188:0 cache_transcript_data - A
    F 500:0 detect_optimal_crop_region - A
    F 1145:0 create_assemblyai_subtitles - A
    C 352:0 CenterCropCalculator - A
    M 433:4 TranscriptLineFormatter.finalize_current_line - A
    M 625:4 OpenCVDNNFaceDetector.__init__ - A
    F 156:0 get_video_transcript - A
    F 215:0 load_cached_transcript_data - A
    F 1449:0 get_available_transitions - A
    C 295:0 TargetDimensionCalculator - A
    M 356:4 CenterCropCalculator.calculate - A
    C 406:0 TranscriptLineFormatter - A
    M 415:4 TranscriptLineFormatter.add_word - A
    C 676:0 HaarCascadeFaceDetector - A
    M 685:4 HaarCascadeFaceDetector.detect - A
    M 798:4 FaceDetectionService.close - A
    F 1464:0 apply_transition_effect - A
    C 107:0 VideoProcessor - A
    M 299:4 TargetDimensionCalculator.calculate - A
    C 558:0 FaceDetector - A
    M 576:4 MediaPipeFaceDetector.__init__ - A
    M 616:4 MediaPipeFaceDetector.close - A
    C 1056:0 SubtitlePositioner - A
    F 278:0 format_ms_to_timestamp - A
    F 286:0 format_ms_to_timestamp_precise - A
    F 495:0 round_to_even - A
    F 1612:0 get_video_transcript_with_assemblyai - A
    F 1621:0 create_9_16_clip - A
    M 110:4 VideoProcessor.__init__ - A
    M 122:4 VideoProcessor.get_optimal_encoding_settings - A
    M 409:4 TranscriptLineFormatter.__init__ - A
    M 447:4 TranscriptLineFormatter.get_formatted_output - A
    M 561:4 FaceDetector.detect - A
    M 679:4 HaarCascadeFaceDetector.__init__ - A
    M 750:4 FaceDetectionService.__init__ - A
    M 1060:4 SubtitlePositioner.calculate_position - A
src/config.py
    M 90:4 Config.get_llm_model - A
    M 127:4 Config._has_cloud_api_key - A
    C 10:0 Config - A
    M 140:4 Config.get_log_level - A
    M 19:4 Config.__init__ - A
    M 110:4 Config._create_local_llm_model - A
src/logging_config.py
    F 120:0 cleanup_old_logs - A
    F 54:0 setup_logging - A
    F 15:0 get_level_emoji - A
    C 37:0 EmojiFormatter - A
    M 40:4 EmojiFormatter.format - A
src/models.py
    C 155:0 Source - A
    M 180:4 Source.decide_source_type - A
    F 22:0 generate_uuid_string - A
    C 27:0 User - A
    C 100:0 Task - A
    C 188:0 GeneratedClip - A
    C 225:0 SystemFont - A
src/database.py
    F 60:0 init_db - C
    F 49:0 get_db - A
    F 114:0 close_db - A
    C 42:0 Base - A
src/ai.py
    F 344:0 get_most_relevant_parts_by_transcript - C
    C 260:0 TranscriptSegmentValidator - B
    M 278:4 TranscriptSegmentValidator.validate_timestamps - B
    M 310:4 TranscriptSegmentValidator.validate_segment - A
    F 101:0 _get_llm_model - A
    C 142:0 CleanStartValidator - A
    C 221:0 TimestampFormatValidator - A
    M 160:4 CleanStartValidator.validate - A
    C 179:0 TimestampParser - A
    M 185:4 TimestampParser.parse_timestamp - A
    M 209:4 TimestampParser.validate_duration - A
    M 230:4 TimestampFormatValidator.validate - A
    M 266:4 TranscriptSegmentValidator.validate_text_content - A
    F 125:0 _get_transcript_agent - A
    M 248:4 TimestampFormatValidator.add_default_milliseconds - A
    F 174:0 validate_clean_start - A
    F 484:0 get_most_relevant_parts_sync - A
    C 19:0 TranscriptSegment - A
    C 37:0 TranscriptAnalysis - A
    M 202:4 TimestampParser.calculate_duration - A
src/ai_structured.py
    F 354:0 analyze_transcript_structured - C
    F 258:0 _validate_and_adjust_segments - C
    F 232:0 _analyze_response_durations - B
    F 18:0 expand_segment_to_duration - A
    F 203:0 build_user_prompt - A
    F 116:0 build_system_prompt - A
    F 223:0 _get_duration - A
    C 90:0 TranscriptSegment - A
    C 108:0 TranscriptAnalysis - A
src/lifecycle.py
    F 41:0 _detect_system_fonts_background - A
    F 53:0 lifespan - A
    F 25:0 initialize_font_service - A
src/transcription_mlx.py
    F 38:0 transcribe_video_mlx - C
    F 235:0 _extract_words_from_result - B
    F 313:0 _reconstruct_words_with_llm - B
    F 414:0 _rebuild_segments_from_words - B
    F 472:0 _align_reconstructed_words - B
    F 196:0 _extract_segments_from_result - B
    F 567:0 load_cached_transcript_mlx - A
    F 180:0 _extract_text_from_result - A
    F 281:0 _get_token_start_time - A
    F 297:0 _get_token_end_time - A
    F 551:0 get_video_transcript_mlx - A
src/main.py
    F 230:0 get_task_details - B
    F 380:0 upload_logo - B
    F 94:0 start_task_with_progress - B
    F 337:0 upload_video - B
    F 177:0 get_task_clips - A
    F 286:0 get_available_transitions - A
    F 69:0 check_database_health - A
    F 317:0 get_default_ai_prompt - A
    F 473:0 run_dev - A
    F 57:0 read_root - A
    F 64:0 health_check - A
    F 79:0 start_task - A
src/youtube_utils.py
    F 115:0 get_youtube_video_id - B
    F 248:0 download_youtube_video - B
    C 20:0 DownloadedFileLocator - A
    F 305:0 is_video_suitable_for_processing - A
    F 330:0 cleanup_downloaded_files - A
    M 26:4 DownloadedFileLocator.find_video_file - A
    F 164:0 get_youtube_video_info - A
    F 220:0 get_youtube_video_title - A
    F 229:0 _perform_download_attempt - A
    F 299:0 get_video_duration - A
    C 41:0 DownloadRetryHandler - A
    C 57:0 YouTubeDownloader - A
    F 158:0 validate_youtube_url - A
    F 346:0 extract_video_id - A
    M 45:4 DownloadRetryHandler.should_retry - A
    M 50:4 DownloadRetryHandler.wait_before_retry - A
    M 60:4 YouTubeDownloader.__init__ - A
    M 64:4 YouTubeDownloader.get_optimal_download_options - A
src/dependencies.py
    F 38:0 get_current_user - B
    F 23:0 get_font_service - A
    F 92:0 get_optional_user - A
    F 32:0 set_font_service - A
src/utils/async_helpers.py
    F 15:0 run_in_thread - A
    F 32:0 async_wrap - A
src/utils/font_options.py
    F 43:0 merge_with_defaults - A
    F 17:0 parse_font_options - A
src/repositories/clip_repository.py
    F 15:0 parse_sqlite_datetime - A
    C 34:0 ClipRepository - A
    M 83:4 ClipRepository.get_clips_by_task - A
    M 132:4 ClipRepository.get_clips_count - A
    M 144:4 ClipRepository.delete_clips_by_task - A
    M 38:4 ClipRepository.create_clip - A
    M 156:4 ClipRepository.delete_clip - A
src/repositories/source_repository.py
    C 12:0 SourceRepository - A
    M 40:4 SourceRepository.get_source_by_id - A
    M 16:4 SourceRepository.create_source - A
    M 65:4 SourceRepository.update_source_title - A
src/repositories/task_repository.py
    M 110:4 TaskRepository.update_task_status - A
    F 15:0 parse_sqlite_datetime - A
    C 34:0 TaskRepository - A
    M 72:4 TaskRepository.get_task_by_id - A
    M 163:4 TaskRepository.get_user_tasks - A
    M 38:4 TaskRepository.create_task - A
    M 145:4 TaskRepository.update_task_clips - A
    M 201:4 TaskRepository.user_exists - A
    M 209:4 TaskRepository.delete_task - A
src/scripts/utility_grimp_analysis.py
    F 90:0 analyze_package - C
    F 31:0 find_circular_dependencies - A
    F 73:0 calculate_coupling_metrics - A
    F 205:0 main - A
src/scripts/utility_xray.py
    F 126:0 main - B
    F 105:0 scan_directory - B
    F 37:0 get_complexity_map - A
    F 48:0 generate_skeleton - A
src/scripts/utility_dependency_graph.py
    F 110:0 main - C
    F 43:0 build_dependency_graph - B
    F 26:0 extract_imports - B
    F 96:0 calculate_coupling - A
    F 68:0 find_cycles - A
src/scripts/utility_complexity_heatmap.py
    F 140:0 main - D
    F 80:0 scan_codebase - B
    F 52:0 analyze_file - A
    C 37:0 FunctionComplexity - A
    C 46:0 FileMetrics - A
src/api/routes/media.py
    F 50:0 upload_video - B
    F 19:0 get_available_transitions - A
src/api/routes/tasks.py
    F 52:0 create_task - B
    F 297:0 delete_task - B
    F 339:0 delete_clip - B
    F 266:0 update_task - A
    F 24:0 list_tasks - A
    F 154:0 get_task - A
    F 173:0 get_task_clips - A
    F 196:0 get_task_progress_sse - A
src/api/routes/fonts.py
    F 124:0 get_font_file - B
    F 52:0 search_fonts - A
    F 19:0 list_fonts - A
    F 90:0 refresh_fonts - A
src/workers/tasks.py
    F 20:0 process_video_task - A
src/workers/local_queue.py
    M 74:4 LocalJobQueue._worker - B
    C 34:0 LocalJobQueue - A
    M 50:4 LocalJobQueue.start_workers - A
    M 161:4 LocalJobQueue.get_job_result - A
    F 181:0 get_job_queue - A
    M 62:4 LocalJobQueue.stop_workers - A
    M 148:4 LocalJobQueue.get_job_status - A
    C 19:0 Job - A
    M 37:4 LocalJobQueue.__init__ - A
    M 115:4 LocalJobQueue.enqueue_job - A
    M 136:4 LocalJobQueue.get_job - A
src/workers/job_queue.py
    C 20:0 JobQueue - A
    M 60:4 JobQueue.enqueue_job - A
    M 31:4 JobQueue.get_pool - A
    M 47:4 JobQueue.close_pool - A
    M 100:4 JobQueue.get_job_status - A
    M 115:4 JobQueue.get_job_result - A
src/workers/local_progress.py
    M 110:4 LocalProgressTracker.subscribe - B
    C 38:0 LocalProgressTracker - A
    M 46:4 LocalProgressTracker.update - A
    F 163:0 get_progress_tracker - A
    C 18:0 Progress - A
    M 27:4 Progress.to_dict - A
    M 41:4 LocalProgressTracker.__init__ - A
    M 78:4 LocalProgressTracker.get - A
    M 90:4 LocalProgressTracker.complete - A
    M 100:4 LocalProgressTracker.error - A
src/services/task_service.py
    M 29:4 TaskService.create_task_with_source - A
    C 18:0 TaskService - A
    M 75:4 TaskService.process_task - A
    M 21:4 TaskService.__init__ - A
    M 188:4 TaskService.get_task_with_clips - A
    M 204:4 TaskService.get_user_tasks - A
    M 210:4 TaskService.delete_task - A
src/services/video_service.py
    M 211:4 VideoService.process_video_complete - C
    C 39:0 VideoProcessingResponse - A
    C 71:0 VideoService - A
    M 75:4 VideoService._get_video_path - A
    M 43:4 VideoProcessingResponse.build_response - A
    M 89:4 VideoService.download_video - A
    M 111:4 VideoService.get_video_title - A
    M 57:4 VideoProcessingResponse.segments_to_json - A
    M 124:4 VideoService.generate_transcript - A
    M 164:4 VideoService.create_video_clips - A
    M 205:4 VideoService.determine_source_type - A
    C 27:0 VideoDownloadError - A
    C 33:0 VideoNotFoundError - A
    M 142:4 VideoService.analyze_transcript - A
src/services/font_service.py
    M 257:4 FontService.validate_font - B
    M 341:4 FontService.cache_fonts - B
    M 159:4 FontService.detect_system_fonts - B
    M 113:4 FontService.get_bundled_fonts - B
    M 415:4 FontService.get_all_fonts - B
    C 96:0 FontService - A
    C 39:0 FontNameExtractor - A
    M 43:4 FontNameExtractor.extract_from_name_table - A
    M 206:4 FontService.extract_font_metadata - A
    C 78:0 FontWeightExtractor - A
    M 317:4 FontService.compute_file_hash - A
    M 82:4 FontWeightExtractor.extract_weight - A
    C 23:0 FontMetadata - A
    M 62:4 FontNameExtractor.extract_all_names - A
    M 99:4 FontService.__init__ - A
    M 481:4 FontService.get_font_by_name - A
    M 495:4 FontService.refresh_system_fonts - A
src/services/user_preferences_service.py
    M 116:4 UserPreferencesService.merge_with_request_options - B
    M 168:4 UserPreferencesService.get_logo_path - B
    C 19:0 UserPreferencesService - A
    M 62:4 UserPreferencesService._merge_with_defaults - A
    M 79:4 UserPreferencesService.get_user_preferences - A
    M 54:4 UserPreferencesService.__init__ - A
src/services/video_service_async.py
    M 113:4 AsyncVideoProcessingService.process_video_async - B
    C 28:0 AsyncVideoProcessingService - A
    M 45:4 AsyncVideoProcessingService.create_task - A
    M 282:4 AsyncVideoProcessingService._update_task_status - A
    M 35:4 AsyncVideoProcessingService.__init__ - A
