


TODO - lets investigate combining filemanager and cleanup_services into one service that will 
        handle both file management and cleanup tasks. The Service will also handle file downloads from the 
        jobsroutes, when fully implemented. this way we can have a single service that manages all file-related
        tasks, including cleanup, downloads, and file management. This will simplify the codebase and make it easier
        to maintain and extend in the future.


TODO - lets create a sub module for ai services this will allow easier integration with OpenRouter and pydantic_ai. 
this also means we plan to handle all ai related tasks in one module. with pydantic_ai we can handle prompting and tool calling 
and also easily integrate with OpenRouter for more advanced ai capabilities.

tools subfolder - this will contain all the tools we use for ai tasks, such as web scraping, data extraction, etc.