/* Various streamlined functions for checking the presence of a cell,
 * depending on whether a null bitmap exists and what the raster cell
 * type is
 * */


#define ___IS_PRESENT(x,y) is_present_##x##_##y
#define __IS_PRESENT(x,y) (x == FCELL_TYPE ? ___IS_PRESENT(FCELL,y) : ___IS_PRESENT(DCELL,y) )
#define _IS_PRESENT(x,y) (x == CELL_TYPE ? ___IS_PRESENT(CELL,y) : __IS_PRESENT(x,y) )
#define IS_PRESENT(x,y) (y == 1 ? _IS_PRESENT(x,nonull) : _IS_PRESENT(x,null) )

int is_present_CELL_null(void* inrast, int col);
int is_present_CELL_nonull(void* inrast, int col);
int is_present_FCELL_null(void* inrast, int col);
int is_present_FCELL_nonull(void* inrast, int col);
int is_present_DCELL_null(void* inrast, int col);
int is_present_DCELL_nonull(void* inrast, int col);
