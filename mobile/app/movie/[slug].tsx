import { useLocalSearchParams } from 'expo-router';
import { ContentDetailScreen } from '@/features/catalog/ContentDetailScreen';
export default function MovieDetail(){const{slug}=useLocalSearchParams<{slug:string}>();return <ContentDetailScreen type="movie" slug={slug}/>}
