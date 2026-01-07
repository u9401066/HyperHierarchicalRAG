"""
Fetch RAG papers from arXiv and insert into HyperHierarchicalRAG
"""
import urllib.request
import xml.etree.ElementTree as ET
import json
import asyncio
from pathlib import Path
from typing import Optional

def fetch_arxiv_papers(query: str = "retrieval augmented generation", max_results: int = 5):
    """Fetch papers from arXiv API."""
    # Use title and abstract search for more relevant results
    query_encoded = query.replace(" ", "+AND+")
    url = f'http://export.arxiv.org/api/query?search_query=ti:{query_encoded}+OR+abs:{query_encoded}&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending'
    
    print(f"Fetching from: {url[:100]}...")
    
    with urllib.request.urlopen(url) as response:
        data = response.read().decode('utf-8')
    
    root = ET.fromstring(data)
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    
    papers = []
    for entry in root.findall('atom:entry', ns):
        title_elem = entry.find('atom:title', ns)
        summary_elem = entry.find('atom:summary', ns)
        id_elem = entry.find('atom:id', ns)
        published_elem = entry.find('atom:published', ns)
        
        if title_elem is None or title_elem.text is None:
            continue
        
        title = title_elem.text.strip().replace('\n', ' ')
        summary = summary_elem.text.strip().replace('\n', ' ') if summary_elem is not None and summary_elem.text else ""
        arxiv_id = id_elem.text.split('/')[-1] if id_elem is not None and id_elem.text else "unknown"
        published = published_elem.text[:10] if published_elem is not None and published_elem.text else "unknown"
        
        authors = []
        for a in entry.findall('atom:author', ns):
            name_elem = a.find('atom:name', ns)
            if name_elem is not None and name_elem.text:
                authors.append(name_elem.text)
        
        papers.append({
            'id': arxiv_id,
            'title': title,
            'authors': authors,
            'published': published,
            'summary': summary
        })
    
    return papers


async def insert_papers_to_rag(papers: list):
    """Insert papers into RAGEngine."""
    from hyperhierarchical_rag.engine import RAGEngine
    
    engine = RAGEngine.from_env()
    await engine.initialize()
    
    results = []
    for paper in papers:
        # Create document text
        doc_text = f"""
Title: {paper['title']}

Authors: {', '.join(paper['authors'])}

Published: {paper['published']}

Abstract:
{paper['summary']}
"""
        result = await engine.insert(text=doc_text, doc_id=f"arxiv:{paper['id']}")
        results.append({
            'paper_id': paper['id'],
            'title': paper['title'],
            'result': result
        })
        print(f"✅ Inserted: {paper['id']} - {paper['title'][:50]}...")
    
    return results


def main():
    print("=" * 60)
    print("Fetching RAG papers from arXiv...")
    print("=" * 60)
    
    papers = fetch_arxiv_papers("retrieval augmented generation", max_results=5)
    
    print(f"\nFound {len(papers)} papers:\n")
    for i, p in enumerate(papers, 1):
        print(f"Paper {i}: {p['id']}")
        print(f"  Title: {p['title'][:80]}...")
        print(f"  Authors: {', '.join(p['authors'][:3])}{'...' if len(p['authors']) > 3 else ''}")
        print(f"  Date: {p['published']}")
        print(f"  Summary: {p['summary'][:200]}...")
        print()
    
    # Save papers to JSON
    output_dir = Path("data/papers")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / "arxiv_rag_papers.json", "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)
    
    print(f"📁 Papers saved to: {output_dir / 'arxiv_rag_papers.json'}")
    
    # Ask to insert
    response = input("\nInsert papers into RAG system? (y/n): ")
    if response.lower() == 'y':
        print("\n" + "=" * 60)
        print("Inserting papers into HyperHierarchicalRAG...")
        print("=" * 60 + "\n")
        results = asyncio.run(insert_papers_to_rag(papers))
        print(f"\n✅ Inserted {len(results)} papers into RAG system!")


if __name__ == "__main__":
    main()
