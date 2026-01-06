# Product Context

## 📋 專案概述

**HyperHierarchicalRAG** 旨在建立一個超越傳統 GraphRAG 的新一代 RAG 模型。它結合了 HGMem 的超圖工作記憶與 LightRAG 的雙層階層檢索技術。

## 🏗️ 參考架構

- **HGMem (MemRAG)**: 提供基於超圖 (Hypergraph) 的動態工作記憶演化機制，適合捕捉 n-ary 關係。
- **LightRAG**: 提供 Local/Global 雙通路的關鍵字檢索與階層式圖譜生成。
- **FWHDNN**: 參考其多尺度 (Multi-scale) 拓撲捕捉技術，用於優化檢索信號。

## 🔧 技術棧

- **核心框架**: Python 3.10+
- **圖儲存**: NetworkX / Neo4j (兼容 LightRAG 介面)
- **向量庫**: NanoVectorDB / Faiss
- **推理引導**: LLM-based multi-step reasoning chains
