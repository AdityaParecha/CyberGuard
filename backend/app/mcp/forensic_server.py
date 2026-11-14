import base64

from mcp.server import MCPServer

from backend.app.services.tsk_service import (
    inspect_partitions,
    inspect_filesystem,
    list_deleted_entries,
    list_filesystem_entries,
    extract_file_content,
)

mcp_server = MCPServer("CyberGuard Forensic Tools")


@mcp_server.tool()
def scan_image_partitions(image_path: str) -> dict:
    """Inspect partitions in a forensic disk image using Sleuth Kit mmls."""
    return inspect_partitions(image_path)


@mcp_server.tool()
def inspect_image_filesystem(
    image_path: str,
    partition_offset: int | None = None,
) -> dict:
    """Inspect filesystem metadata using Sleuth Kit fsstat."""
    return inspect_filesystem(image_path, partition_offset)


@mcp_server.tool()
def list_image_files(
    image_path: str,
    partition_offset: int | None = None,
) -> dict:
    """List filesystem entries recursively using Sleuth Kit fls."""
    return list_filesystem_entries(image_path, partition_offset)


@mcp_server.tool()
def list_deleted_image_files(
    image_path: str,
    partition_offset: int | None = None,
) -> dict:
    """List deleted filesystem entries using Sleuth Kit fls."""
    return list_deleted_entries(image_path, partition_offset)


@mcp_server.tool()
def extract_image_file(
    image_path: str,
    metadata_address: int,
    partition_offset: int | None = None,
    max_bytes: int = 10485760,
) -> dict:
    """Extract file content using Sleuth Kit icat.

    Text data is returned as UTF-8. Non-text data is returned as base64.
    """
    result = extract_file_content(
        image_path=image_path,
        metadata_address=metadata_address,
        partition_offset=partition_offset,
        max_bytes=max_bytes,
    )

    content = result.pop("content", None)

    if content is not None:
        try:
            result["content_text"] = content.decode("utf-8")
            result["content_encoding"] = "utf-8"
        except UnicodeDecodeError:
            result["content_base64"] = base64.b64encode(content).decode("ascii")
            result["content_encoding"] = "base64"

    return result


if __name__ == "__main__":
    mcp_server.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8100,
    )