"""
Document processing functionality for RAGAnything

Contains methods for parsing documents and processing multimodal content
"""

import os
import asyncio
from typing import Dict, List, Any, Tuple
from pathlib import Path
from raganything.mineru_parser import MineruParser
from raganything.utils import (
    separate_content,
    insert_text_content,
    get_processor_for_type,
)


class ProcessorMixin:
    """ProcessorMixin class containing document processing functionality for RAGAnything"""

    async def parse_document(
        self,
        file_path: str,
        output_dir: str = None,
        parse_method: str = None,
        display_stats: bool = None,
        progress_callback=None,
        **kwargs,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Parse document using MinerU with real-time progress feedback

        Args:
            file_path: Path to the file to parse
            output_dir: Output directory (defaults to config.mineru_output_dir)
            parse_method: Parse method (defaults to config.mineru_parse_method)
            display_stats: Whether to display content statistics (defaults to config.display_content_stats)
            progress_callback: Optional callback function to report parsing progress
            **kwargs: Additional parameters for MinerU parser (e.g., lang, device, start_page, end_page, formula, table, backend, source)

        Returns:
            (content_list, md_content): Content list and markdown text
        """
        # Use config defaults if not provided
        if output_dir is None:
            output_dir = self.config.mineru_output_dir
        if parse_method is None:
            parse_method = self.config.mineru_parse_method
        if display_stats is None:
            display_stats = self.config.display_content_stats

        self.logger.info(f"Starting document parsing: {file_path}")

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Choose appropriate parsing method based on file extension
        ext = file_path.suffix.lower()

        try:
            if ext in [".pdf"]:
                self.logger.info(f"Detected PDF file, using PDF parser (method={parse_method})...")
                
                # 🔧 修复：根据是否有 progress_callback 选择不同的解析方法
                if progress_callback:
                    # 使用流式解析方法以支持实时进度
                    self.logger.info("Using streaming parser for real-time progress...")
                    content_list, md_content = await MineruParser.parse_pdf_streaming(
                        pdf_path=file_path,
                        output_dir=output_dir,
                        method=parse_method,
                        progress_callback=progress_callback,
                        **kwargs,
                    )
                else:
                    # 没有进度回调时使用普通方法
                    content_list, md_content = MineruParser.parse_pdf(
                        pdf_path=file_path,
                        output_dir=output_dir,
                        method=parse_method,
                        **kwargs,
                    )
            elif ext in [
                ".jpg",
                ".jpeg",
                ".png",
                ".bmp",
                ".tiff",
                ".tif",
                ".gif",
                ".webp",
            ]:
                self.logger.info("Detected image file, using image parser...")
                content_list, md_content = MineruParser.parse_image(
                    image_path=file_path, output_dir=output_dir, **kwargs
                )
            elif ext in [".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"]:
                self.logger.info("Detected Office document, using Office parser...")
                content_list, md_content = MineruParser.parse_office_doc(
                    doc_path=file_path, output_dir=output_dir, **kwargs
                )
            else:
                # For other or unknown formats, use generic parser
                self.logger.info(
                    f"Using generic parser for {ext} file (method={parse_method})..."
                )
                content_list, md_content = MineruParser.parse_document(
                    file_path=file_path,
                    method=parse_method,
                    output_dir=output_dir,
                    **kwargs,
                )

        except Exception as e:
            self.logger.error(f"Error during parsing with specific parser: {str(e)}")
            self.logger.warning("Falling back to generic parser...")
            # If specific parser fails, fall back to generic parser
            content_list, md_content = MineruParser.parse_document(
                file_path=file_path,
                method=parse_method,
                output_dir=output_dir,
                **kwargs,
            )

        self.logger.info(
            f"Parsing complete! Extracted {len(content_list)} content blocks"
        )
        self.logger.info(f"Markdown text length: {len(md_content)} characters")

        # Display content statistics if requested
        if display_stats:
            self.logger.info("\nContent Information:")
            self.logger.info(f"* Total blocks in content_list: {len(content_list)}")
            self.logger.info(f"* Markdown content length: {len(md_content)} characters")

            # Count elements by type
            block_types: Dict[str, int] = {}
            for block in content_list:
                if isinstance(block, dict):
                    block_type = block.get("type", "unknown")
                    if isinstance(block_type, str):
                        block_types[block_type] = block_types.get(block_type, 0) + 1

            self.logger.info("* Content block types:")
            for block_type, count in block_types.items():
                self.logger.info(f"  - {block_type}: {count}")

        return content_list, md_content

    async def _process_multimodal_content(
        self, multimodal_items: List[Dict[str, Any]], file_path: str
    ):
        """
        Process multimodal content (using specialized processors)

        Args:
            multimodal_items: List of multimodal items
            file_path: File path (for reference)
        """
        if not multimodal_items:
            self.logger.debug("No multimodal content to process")
            return

        self.logger.info("Starting multimodal content processing...")

        file_name = os.path.basename(file_path)

        # Collect all chunk results for batch processing (similar to text content processing)
        all_chunk_results = []

        for i, item in enumerate(multimodal_items):
            try:
                content_type = item.get("type", "unknown")
                self.logger.info(
                    f"Processing item {i+1}/{len(multimodal_items)}: {content_type} content"
                )

                # Select appropriate processor
                processor = get_processor_for_type(self.modal_processors, content_type)

                if processor:
                    # Prepare item info for context extraction
                    item_info = {
                        "page_idx": item.get("page_idx", 0),
                        "index": i,
                        "type": content_type,
                    }

                    # Process content and get chunk results instead of immediately merging
                    (
                        enhanced_caption,
                        entity_info,
                        chunk_results,
                    ) = await processor.process_multimodal_content(
                        modal_content=item,
                        content_type=content_type,
                        file_path=file_name,
                        item_info=item_info,  # Pass item info for context extraction
                        batch_mode=True,
                    )

                    # Collect chunk results for batch processing
                    all_chunk_results.extend(chunk_results)

                    self.logger.info(
                        f"{content_type} processing complete: {entity_info.get('entity_name', 'Unknown')}"
                    )
                else:
                    self.logger.warning(
                        f"No suitable processor found for {content_type} type content"
                    )

            except Exception as e:
                self.logger.error(f"Error processing multimodal content: {str(e)}")
                self.logger.debug("Exception details:", exc_info=True)
                continue

        # Batch merge all multimodal content results (similar to text content processing)
        if all_chunk_results:
            from lightrag.operate import merge_nodes_and_edges
            from lightrag.kg.shared_storage import (
                get_namespace_data,
                get_pipeline_status_lock,
            )

            # Get pipeline status and lock from shared storage
            pipeline_status = await get_namespace_data("pipeline_status")
            pipeline_status_lock = get_pipeline_status_lock()

            await merge_nodes_and_edges(
                chunk_results=all_chunk_results,
                knowledge_graph_inst=self.lightrag.chunk_entity_relation_graph,
                entity_vdb=self.lightrag.entities_vdb,
                relationships_vdb=self.lightrag.relationships_vdb,
                global_config=self.lightrag.__dict__,
                pipeline_status=pipeline_status,
                pipeline_status_lock=pipeline_status_lock,
                llm_response_cache=self.lightrag.llm_response_cache,
                current_file_number=1,
                total_files=1,
                file_path=file_name,
            )

            await self.lightrag._insert_done()

        self.logger.info("Multimodal content processing complete")

    async def process_document_complete(
        self,
        file_path: str,
        output_dir: str = None,
        parse_method: str = None,
        display_stats: bool = None,
        split_by_character: str | None = None,
        split_by_character_only: bool = False,
        doc_id: str | None = None,
        progress_callback=None,
        **kwargs,
    ):
        """
        Complete document processing workflow

        Args:
            file_path: Path to the file to process
            output_dir: MinerU output directory (defaults to config.mineru_output_dir)
            parse_method: Parse method (defaults to config.mineru_parse_method)
            display_stats: Whether to display content statistics (defaults to config.display_content_stats)
            split_by_character: Optional character to split the text by
            split_by_character_only: If True, split only by the specified character
            doc_id: Optional document ID, if not provided MD5 hash will be generated
            progress_callback: Optional callback function to report progress (progress, message)
            **kwargs: Additional parameters for MinerU parser (e.g., lang, device, start_page, end_page, formula, table, backend, source)
        """
        # Helper function to safely call progress callback
        async def report_progress(progress: int, message: str):
            if progress_callback:
                try:
                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback(progress, message)
                    else:
                        progress_callback(progress, message)
                except Exception as e:
                    self.logger.warning(f"Progress callback error: {e}")
        # Ensure LightRAG is initialized
        await self._ensure_lightrag_initialized()

        # Use config defaults if not provided
        if output_dir is None:
            output_dir = self.config.mineru_output_dir
        if parse_method is None:
            parse_method = self.config.mineru_parse_method
        if display_stats is None:
            display_stats = self.config.display_content_stats

        self.logger.info(f"Starting complete document processing: {file_path}")
        await report_progress(10, f"开始解析文档: {os.path.basename(file_path)}")

        # Step 1: Parse document using MinerU
        await report_progress(20, "正在使用MinerU解析文档...")
        content_list, md_content = await self.parse_document(
            file_path, output_dir, parse_method, display_stats, progress_callback=progress_callback, **kwargs
        )
        await report_progress(70, f"MinerU解析完成，提取了 {len(content_list)} 个内容块")

        # Step 2: Separate text and multimodal content
        await report_progress(72, "正在分离文本和多模态内容...")
        text_content, multimodal_items = separate_content(content_list)
        await report_progress(75, f"内容分离完成: 文本长度 {len(text_content)}, 多模态项目 {len(multimodal_items)}")

        # Step 2.5: Set content source for context extraction in multimodal processing
        if hasattr(self, "set_content_source_for_context") and multimodal_items:
            await report_progress(78, "设置多模态处理的上下文源...")
            self.logger.info(
                "Setting content source for context-aware multimodal processing..."
            )
            self.set_content_source_for_context(
                content_list, self.config.content_format
            )

        # Step 3: Insert pure text content with all parameters
        if text_content.strip():
            await report_progress(80, "正在插入文本内容到知识图谱...")
            file_name = os.path.basename(file_path)
            await insert_text_content(
                self.lightrag,
                text_content,
                file_paths=file_name,
                split_by_character=split_by_character,
                split_by_character_only=split_by_character_only,
                ids=doc_id,
            )
            await report_progress(90, "文本内容插入完成")

        # Step 4: Process multimodal content (using specialized processors)
        if multimodal_items:
            await report_progress(92, f"正在处理 {len(multimodal_items)} 个多模态内容项...")
            await self._process_multimodal_content(multimodal_items, file_path)
            await report_progress(98, "多模态内容处理完成")

        await report_progress(100, "文档处理完全完成！")
        self.logger.info(f"Document {file_path} processing complete!")
