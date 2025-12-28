File: src/video_utils.py
  Class: VideoProcessor (107:0)
    Function: __init__ 4/4 100.00%
    Function: get_optimal_encoding_settings 0/4 0.00%
    Total: 50.0%
  Class: TargetDimensionCalculator (295:0)
    Function: calculate staticmethod
    Total: 0.0%
  Class: FaceCenteredCropCalculator (312:0)
    Function: calculate staticmethod
    Total: 0.0%
  Class: CenterCropCalculator (352:0)
    Function: calculate staticmethod
    Total: 0.0%
  Class: TranscriptLineBreaker (369:0)
    Function: should_break_line staticmethod
    Total: 0.0%
  Class: TranscriptLineFormatter (406:0)
    Function: __init__ 3/3 100.00%
    Function: add_word 2/3 66.67%
    Function: finalize_current_line 3/3 100.00%
    Function: get_formatted_output 1/3 33.33%
    Total: 75.0%
  Class: FaceDetector (558:0)
    Function: detect 0/0 0.00%
    Total: 0.0%
  Class: MediaPipeFaceDetector (573:0)
    Function: __init__ 1/1 100.00%
    Function: detect 1/1 100.00%
    Function: close 1/1 100.00%
    Total: 100.0%
  Class: OpenCVDNNFaceDetector (622:0)
    Function: __init__ 1/1 100.00%
    Function: detect 1/1 100.00%
    Total: 100.0%
  Class: HaarCascadeFaceDetector (676:0)
    Function: __init__ 1/1 100.00%
    Function: detect 1/1 100.00%
    Total: 100.0%
  Class: VideoFrameSampler (712:0)
    Function: generate_sample_times staticmethod
    Total: 0.0%
  Class: FaceDetectionService (744:0)
    Function: __init__ 1/3 33.33%
    Function: detect_in_frame 3/3 100.00%
    Function: close 1/3 33.33%
    Total: 55.56%
  Class: SubtitleWordFilter (916:0)
    Function: get_relevant_words staticmethod
    Total: 0.0%
  Class: SubtitleTextClipCreator (948:0)
    Function: create_text_clip staticmethod
    Total: 0.0%
  Class: SubtitlePositioner (1056:0)
    Function: calculate_position staticmethod
    Total: 0.0%
  Class: SubtitleClipBuilder (1066:0)
    Function: build_clips staticmethod
    Total: 0.0%
File: src/config.py
  Class: Config (10:0)
    Function: __init__ 26/26 100.00%
    Function: get_llm_model 2/26 7.69%
    Function: _create_local_llm_model 3/26 11.54%
    Function: _has_cloud_api_key 4/26 15.38%
    Function: get_log_level 1/26 3.85%
    Total: 27.69%
File: src/logging_config.py
  Class: EmojiFormatter (37:0)
    Function: format 0/0 0.00%
    Total: 0.0%
File: src/models.py
  Class: User (27:0)
    Total: 0.0%
  Class: Task (100:0)
    Total: 0.0%
  Class: Source (155:0)
    Function: decide_source_type 0/2 0.00%
    Total: 0.0%
  Class: GeneratedClip (188:0)
    Total: 0.0%
  Class: SystemFont (225:0)
    Total: 0.0%
File: src/database.py
  Class: Base (42:0)
    Total: 0.0%
File: src/ai.py
  Class: TranscriptSegment (19:0)
    Total: 0.0%
  Class: TranscriptAnalysis (37:0)
    Total: 0.0%
  Class: CleanStartValidator (142:0)
    Function: validate staticmethod
    Total: 0.0%
  Class: TimestampParser (179:0)
    Function: parse_timestamp staticmethod
    Function: calculate_duration staticmethod
    Function: validate_duration staticmethod
    Total: 0.0%
  Class: TimestampFormatValidator (221:0)
    Function: validate staticmethod
    Function: add_default_milliseconds staticmethod
    Total: 0.0%
  Class: TranscriptSegmentValidator (260:0)
    Function: validate_text_content staticmethod
    Function: validate_timestamps staticmethod
    Function: validate_segment staticmethod
    Total: 0.0%
File: src/__init__.py
File: src/ai_structured.py
  Class: TranscriptSegment (90:0)
    Total: 0.0%
  Class: TranscriptAnalysis (108:0)
    Total: 0.0%
File: src/lifecycle.py
File: src/transcription_mlx.py
File: src/main.py
File: src/youtube_utils.py
  Class: DownloadedFileLocator (20:0)
    Function: find_video_file staticmethod
    Total: 0.0%
  Class: DownloadRetryHandler (41:0)
    Function: should_retry staticmethod
    Function: wait_before_retry staticmethod
    Total: 0.0%
  Class: YouTubeDownloader (57:0)
    Function: __init__ 1/1 100.00%
    Function: get_optimal_download_options 1/1 100.00%
    Total: 100.0%
File: src/dependencies.py
File: src/utils/async_helpers.py
File: src/utils/__init__.py
File: src/utils/font_options.py
File: src/repositories/clip_repository.py
  Class: ClipRepository (34:0)
    Total: 0.0%
File: src/repositories/source_repository.py
  Class: SourceRepository (12:0)
    Total: 0.0%
File: src/repositories/__init__.py
File: src/repositories/task_repository.py
  Class: TaskRepository (34:0)
    Total: 0.0%
File: src/scripts/utility_grimp_analysis.py
File: src/scripts/utility_xray.py
  Class: SkeletonVisitor (59:4)
    Function: log 1/1 100.00%
    Function: visit_Import 0/1 0.00%
    Function: visit_ImportFrom 0/1 0.00%
    Function: visit_ClassDef 1/1 100.00%
    Function: visit_FunctionDef 1/1 100.00%
    Function: visit_AsyncFunctionDef 1/1 100.00%
    Total: 66.67%
File: src/scripts/utility_dependency_graph.py
File: src/scripts/utility_complexity_heatmap.py
  Class: FunctionComplexity (37:0)
    Total: 0.0%
  Class: FileMetrics (46:0)
    Total: 0.0%
File: src/api/__init__.py
File: src/api/routes/media.py
File: src/api/routes/tasks.py
File: src/api/routes/__init__.py
File: src/api/routes/fonts.py
File: src/workers/tasks.py
File: src/workers/__init__.py
File: src/workers/local_queue.py
  Class: Job (19:0)
    Total: 0.0%
  Class: LocalJobQueue (34:0)
    Function: __init__ 5/5 100.00%
    Function: get_job 1/5 20.00%
    Function: get_job_status 0/5 0.00%
    Function: get_job_result 0/5 0.00%
    Total: 30.0%
File: src/workers/job_queue.py
  Class: JobQueue (20:0)
    Total: 0.0%
File: src/workers/local_progress.py
  Class: Progress (18:0)
    Function: to_dict 5/5 100.00%
    Total: 100.0%
  Class: LocalProgressTracker (38:0)
    Function: __init__ 2/2 100.00%
    Function: get 1/2 50.00%
    Total: 75.0%
File: src/services/task_service.py
  Class: TaskService (18:0)
    Function: __init__ 6/6 100.00%
    Total: 100.0%
File: src/services/video_service.py
  Class: VideoDownloadError (27:0)
    Total: 0.0%
  Class: VideoNotFoundError (33:0)
    Total: 0.0%
  Class: VideoProcessingResponse (39:0)
    Function: build_response staticmethod
    Function: segments_to_json staticmethod
    Total: 0.0%
  Class: VideoService (71:0)
    Function: determine_source_type staticmethod
    Total: 0.0%
File: src/services/__init__.py
File: src/services/font_service.py
  Class: FontMetadata (23:0)
    Total: 0.0%
  Class: FontNameExtractor (39:0)
    Function: extract_from_name_table staticmethod
    Function: extract_all_names staticmethod
    Total: 0.0%
  Class: FontWeightExtractor (78:0)
    Function: extract_weight staticmethod
    Total: 0.0%
  Class: FontService (96:0)
    Function: __init__ 3/3 100.00%
    Total: 100.0%
File: src/services/user_preferences_service.py
  Class: UserPreferencesService (19:0)
    Function: __init__ 1/3 33.33%
    Function: _merge_with_defaults 2/3 66.67%
    Function: get_logo_path 0/3 0.00%
    Total: 33.33%
File: src/services/video_service_async.py
  Class: AsyncVideoProcessingService (28:0)
    Function: __init__ 2/2 100.00%
    Total: 100.0%
